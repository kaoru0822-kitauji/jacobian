import REPL.Snapshots

open Lean REPL

structure ProofStateBounds where
  pickle_path : String
  request_id : String
  max_goals : Nat
  max_local_declarations : Nat
  max_rendered_bytes : Nat
  deriving FromJson

def readBounds : IO ProofStateBounds := do
  let some path ← IO.getEnv "JACOBIAN_LEAN_PROOF_STATE_QUERY"
    | throw <| IO.userError "JACOBIAN_LEAN_PROOF_STATE_QUERY is required"
  let contents ← IO.FS.readFile path
  let json ← match Json.parse contents with
    | .ok value => pure value
    | .error detail => throw <| IO.userError detail
  match fromJson? json with
  | .ok bounds => pure bounds
  | .error detail => throw <| IO.userError detail

def binderInfoName : BinderInfo → String
  | .default => "DEFAULT"
  | .implicit => "IMPLICIT"
  | .strictImplicit => "STRICT_IMPLICIT"
  | .instImplicit => "INSTANCE_IMPLICIT"

def renderedExpr (expr : Expr) : MetaM String := do
  return (← Meta.ppExpr (← instantiateMVars expr)).pretty

def localDeclarationJson (decl : LocalDecl) : MetaM Json := do
  let type ← renderedExpr decl.type
  let value ← decl.value?.mapM renderedExpr
  return Json.mkObj [
    ("user_name", toJson decl.userName.toString),
    ("binder_info", toJson (binderInfoName decl.binderInfo)),
    ("type", toJson type),
    ("value", toJson value)
  ]

def goalJson (goal : MVarId) (index maxLocals : Nat) : MetaM Json :=
  goal.withContext do
    let target ← renderedExpr (← goal.getType)
    let mut locals : Array Json := #[]
    for decl in ← getLCtx do
      if decl.isImplementationDetail then continue
      if locals.size == maxLocals then
        throwError "LEAN_PROOF_STATE_LOCAL_LIMIT"
      locals := locals.push (← localDeclarationJson decl)
    return Json.mkObj [
      ("goal_index", toJson index),
      ("target_type", toJson target),
      ("local_declarations", toJson locals)
    ]

def resultEnvelope (requestId : String) (payload : Json) : Json :=
  Json.mkObj [
    ("request_id", toJson requestId),
    ("payload", payload)
  ]

def errorEnvelope (requestId code message : String) : Json :=
  Json.mkObj [
    ("request_id", toJson requestId),
    ("code", toJson code),
    ("message", toJson message)
  ]

def emit (marker : String) (payload : Json) : IO Unit := do
  let stdout ← IO.getStdout
  stdout.putStrLn s!"{marker} {payload.compress}"
  stdout.flush

unsafe def runQuery (bounds : ProofStateBounds) : IO Json := do
  if bounds.max_goals == 0 || bounds.max_goals > 64 ||
      bounds.max_local_declarations == 0 ||
      bounds.max_local_declarations > 256 ||
      bounds.max_rendered_bytes < 1024 ||
      bounds.max_rendered_bytes > 262144 then
    throw <| IO.userError "LEAN_PROOF_STATE_INVALID_BOUNDS"
  -- This helper is one-shot. Let process exit release the compacted region:
  -- freeing it while multiple goals share local declarations can invalidate
  -- expressions before their JSON rendering is emitted.
  let (snapshot, _) ← ProofSnapshot.unpickle bounds.pickle_path none
  if snapshot.tacticState.goals.length > bounds.max_goals then
    throw <| IO.userError "LEAN_PROOF_STATE_GOAL_LIMIT"
  let (goals, _) ← snapshot.runMetaM do
    snapshot.tacticState.goals.toArray.mapIdxM fun index goal =>
      goalJson goal index bounds.max_local_declarations
  let payload := Json.mkObj [
    ("expression_serialization", "LEAN_PRETTY_PRINTED_EXPR"),
    ("typed_goals", toJson goals)
  ]
  if payload.compress.toUTF8.size > bounds.max_rendered_bytes then
    throw <| IO.userError "LEAN_PROOF_STATE_OUTPUT_LIMIT"
  return payload

unsafe def main : IO Unit := do
  initSearchPath (← Lean.findSysroot)
  let bounds ← readBounds
  try
    emit "JACOBIAN_PROOF_STATE_RESULT" <|
      resultEnvelope bounds.request_id (← runQuery bounds)
  catch error =>
    let message := toString error
    let code :=
      if message.contains "LEAN_PROOF_STATE_GOAL_LIMIT" then
        "LEAN_PROOF_STATE_GOAL_LIMIT"
      else if message.contains "LEAN_PROOF_STATE_LOCAL_LIMIT" then
        "LEAN_PROOF_STATE_LOCAL_LIMIT"
      else if message.contains "LEAN_PROOF_STATE_OUTPUT_LIMIT" then
        "LEAN_PROOF_STATE_OUTPUT_LIMIT"
      else
        "LEAN_PROOF_STATE_QUERY_FAILED"
    emit "JACOBIAN_PROOF_STATE_ERROR" <|
      errorEnvelope bounds.request_id code "typed proof-state extraction failed"
