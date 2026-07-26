import {{JACOBIAN_IMPORT}}
import Lean.DeclarationRange
import Lean.DocString
import Lean.Elab.Command

open Lean

structure DeclarationQuery where
  operation : String
  declaration_name : Option String
  name_contains : Option String
  type_constants : Array String
  namespace_prefixes : Array String
  target_module_prefixes : Array String
  kinds : Array String
  limit : Nat
  deriving FromJson

def declarationKind : ConstantInfo → String
  | .axiomInfo _ => "AXIOM"
  | .defnInfo _ => "DEFINITION"
  | .thmInfo _ => "THEOREM"
  | .opaqueInfo _ => "OPAQUE"
  | .quotInfo _ => "QUOTIENT"
  | .inductInfo _ => "INDUCTIVE"
  | .ctorInfo _ => "CONSTRUCTOR"
  | .recInfo _ => "RECURSOR"

def moduleContaining? (env : Environment) (declName : Name) : Option Name := do
  let some moduleIdx := env.getModuleIdxFor? declName
    | none
  env.allImportedModuleNames[moduleIdx]?

def declarationNamespace (name : Name) : Option String :=
  let ns := name.getPrefix
  if ns.isAnonymous then none else some ns.toString

def sourceJson (env : Environment) (name : Name) :
    Elab.Command.CommandElabM Json := do
  let ranges ← findDeclarationRanges? name
  return match ranges with
    | none => Json.null
    | some ranges =>
      Json.mkObj [
        ("module", toJson ((moduleContaining? env name).map toString)),
        ("line", toJson ranges.selectionRange.pos.line),
        ("column", toJson ranges.selectionRange.pos.column),
        ("end_line", toJson ranges.selectionRange.endPos.line),
        ("end_column", toJson ranges.selectionRange.endPos.column)
      ]

def renderedType (info : ConstantInfo) :
    Elab.Command.CommandElabM String :=
  Elab.Command.liftTermElabM do
    return (← Meta.ppExpr info.type).pretty

def namespaceMatches (query : DeclarationQuery) (name : Name) : Bool :=
  query.namespace_prefixes.isEmpty ||
    query.namespace_prefixes.any fun nsPrefix =>
      name.toString == nsPrefix || name.toString.startsWith (nsPrefix ++ ".")

def kindMatches (query : DeclarationQuery) (info : ConstantInfo) : Bool :=
  query.kinds.isEmpty || query.kinds.contains (declarationKind info)

def targetModuleMatches (query : DeclarationQuery) (env : Environment)
    (name : Name) : Bool :=
  match moduleContaining? env name with
  | none => false
  | some modName =>
    query.target_module_prefixes.isEmpty ||
      query.target_module_prefixes.any fun modulePrefix =>
        modName.toString == modulePrefix ||
          modName.toString.startsWith (modulePrefix ++ ".")

def typeMatches (query : DeclarationQuery) (info : ConstantInfo) : Bool :=
  let used := info.type.getUsedConstantsAsSet
  query.type_constants.all fun constant => used.contains constant.toName

def declarationJson (env : Environment) (name : Name) (info : ConstantInfo)
    (type : String) (matchReasons : Array String) (includeDetails : Bool) :
    Elab.Command.CommandElabM Json := do
  let source ← sourceJson env name
  let docString ←
    if includeDetails then findDocString? env name else pure none
  return Json.mkObj [
    ("name", toJson name.toString),
    ("type", toJson type),
    ("kind", toJson (declarationKind info)),
    ("namespace", toJson (declarationNamespace name)),
    ("docstring", toJson docString),
    ("source", source),
    ("match_reasons", toJson matchReasons)
  ]

def readQuery : IO DeclarationQuery := do
  let some path ← IO.getEnv "JACOBIAN_LEAN_QUERY_FILE"
    | throw <| IO.userError "JACOBIAN_LEAN_QUERY_FILE is required"
  let contents ← IO.FS.readFile path
  let json ← match Json.parse contents with
    | .ok json => pure json
    | .error detail => throw <| IO.userError s!"invalid query JSON: {detail}"
  match fromJson? json with
  | .ok query => pure query
  | .error detail => throw <| IO.userError s!"invalid query contract: {detail}"

run_cmd do
  let query ← readQuery
  let env ← getEnv
  if query.limit == 0 || query.limit > 50 then
    throwError "limit must be between 1 and 50"
  let output ←
    if query.operation == "inspect" then
      let some rawName := query.declaration_name
        | throwError "declaration_name is required"
      let some (name, info) := env.constants.toList.find? fun (name, _) =>
          name.toString == rawName
        | throwError s!"declaration not found: {rawName}"
      if !targetModuleMatches query env name then
        throwError s!"declaration not found: {rawName}"
      let type ← renderedType info
      let declaration ← declarationJson env name info type #[] true
      pure <| Json.mkObj [
        ("operation", "inspect"),
        ("declaration", declaration)
      ]
    else if query.operation == "search" then
      if query.name_contains.isNone && query.type_constants.isEmpty then
        throwError "name_contains or type_constants is required"
      let names := env.constants.toList.toArray.map (·.1) |>.qsort Name.lt
      let mut results : Array Json := #[]
      let mut scanned := 0
      let mut stopReason := "EXHAUSTED"
      for name in names do
        if results.size == query.limit then
          stopReason := "RESULT_LIMIT"
          break
        if isPrivateName name || !targetModuleMatches query env name then continue
        scanned := scanned + 1
        let some info := env.find? name | continue
        if !namespaceMatches query name || !kindMatches query info then continue
        let nameMatched :=
          query.name_contains.map (name.toString.contains ·) |>.getD true
        if !nameMatched || !typeMatches query info then continue
        let type ← renderedType info
        let mut reasons : Array String := #[]
        if query.name_contains.isSome then
          reasons := reasons.push "NAME_SUBSTRING"
        if !query.type_constants.isEmpty then
          reasons := reasons.push "TYPE_CONSTANTS"
        results := results.push (← declarationJson env name info type reasons false)
      pure <| Json.mkObj [
        ("operation", "search"),
        ("declarations", toJson results),
        ("scanned_declarations", scanned),
        ("stop_reason", stopReason)
      ]
    else
      throwError "operation must be search or inspect"
  IO.println s!"JACOBIAN_DECLARATION_RESULT {output.compress}"
