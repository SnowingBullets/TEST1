from policies import Policy
import json
import logging
from vakt import Policy as VaktPolicy
from vakt.rules import Any, Truthy, Falsy, Eq, NotEq, Less, LessOrEqual, Greater, GreaterOrEqual, In, NotIn
from vakt.effects import ALLOW_ACCESS, DENY_ACCESS

# Configure logging
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(message)s')

class PolicyError(Exception):
  pass

def log_event(user, resource, action, result):
    logging.info(f"User: {user}, Resource: {resource}, Action: {action}, Result: {result}")

def get_vakt_rule(definition: dict):
  for k, v in definition.items():
    match k:
      case 'eq':
        if isinstance(v, bool):
          return Falsy() if v == False else Truthy()
        cls = Eq
      case 'neq':
        if isinstance(v, bool):
          return Truthy() if v == False else Falsy()
        cls = NotEq
      case 'lt':
        cls = Less
      case 'leq':
        cls = LessOrEqual
      case 'gt':
        cls = Greater
      case 'geq':
        cls = GreaterOrEqual
      case 'in':
        cls = In
      case 'not-in':
        cls = NotIn
      case _:
        raise PolicyError(f"Unable to convert policy: encountered unrecognised condition {k}")
    if isinstance(v, list):
      return cls(*v)
    return cls(v)
  raise PolicyError(f"Unable to convert policy: empty definition")

def get_vakt_attributes(obj):
  if isinstance(obj, str) and obj == '*':
    return Any()
  res = {}
  for k, v in obj.items():
    if isinstance(v, bool):
      res[k] = Falsy() if v == False else Truthy()
    elif isinstance(v, str):
      res[k] = Any() if v == '*' else Eq(v)
    elif isinstance(v, int):
      res[k] = Eq(v)
    elif isinstance(v, dict):
      res[k] = get_vakt_rule(v)
  return res

def policy_to_vakt(p: Policy) -> VaktPolicy:
    effect = ALLOW_ACCESS if p.effect == 'allow' else DENY_ACCESS
    subjects = [Any()] if p.subject == '*' or len(p.subject) == 0 else [get_vakt_attributes(p.subject)]
    resources = [Any()] if p.resource == '*' or len(p.resource) == 0 else [get_vakt_attributes(p.resource)]
    actions = [Any()] if p.action == '*' or len(p.action) == 0 else [get_vakt_attributes(p.action)]
    context = get_vakt_attributes(p.context) if len(p.context) > 0 else {}
    return VaktPolicy(uid=p.id, subjects=subjects, effect=effect, resources=resources, actions=actions, context=context)
  
def update_task_result(task_id, result):
    with open('config/tasks.json', 'r') as file:
        tasks_data = json.load(file)
    
    for task in tasks_data["tasks"]:
        if task["id"] == task_id:
            task["result"] = "allowed" if result else "denied"
            break
    
    with open('config/tasks.json', 'w') as file:
        json.dump(tasks_data, file, indent=4)