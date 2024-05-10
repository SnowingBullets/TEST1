import logging
import json
from policies import PolicyStore
from vakt import Policy, Inquiry, Guard, RulesChecker
from vakt.storage.memory import MemoryStorage
from socketserver import BaseRequestHandler, ThreadingTCPServer
from vakt.rules.base import Rule
from vakt_util import log_event, policy_to_vakt, update_task_result

# Define custom rule for access level checking
class AccessLevelRule(Rule):
    def satisfied(self, what, inquiry):
        return inquiry.subject.get('access_level', 0) >= what

# Load policies
with open('config/policies.json', 'r') as file:
    policies_data = json.load(file)

# Configure logging
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(message)s')

class LogGuard(Guard):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class VaktHandler(BaseRequestHandler):
    def handle(self):
        res = self.request.recv(512)
        print(res)

# Create storage and add policies
storage = MemoryStorage()
for policy_data in policies_data:
    policy = Policy(
        uid=policy_data['id'],
        description=policy_data.get('description', ''),
        effect=policy_data.get('effect', 'deny'),  # default to 'deny' if effect is not specified
        subjects=policy_data.get('subject', {}),
        actions=policy_data.get('action', {}),
        resources=policy_data.get('resource', {}),
        context=policy_data.get('context', {})
    )
    storage.add(policy)

checker = RulesChecker()
guard = Guard(storage, checker)

# Load tasks
with open('config/tasks.json', 'r') as file:
    tasks_data = json.load(file)
    
# Load users
with open('config/users.json', 'r') as file:
    users_data = json.load(file)

# Load resources
with open('config/resources.json', 'r') as file:
    resources_data = json.load(file)

def get_resource_access_level(resource_id):
    for resource in resources_data['resources']:
        if resource['id'] == resource_id:
            return resource.get('access_level', 0)
    return 0

def log_policies(storage):
    policies = storage.get_all(limit=100, offset=0)
    for policy in policies:
        logging.info(f"Policy ID: {policy.uid}, Effect: {policy.effect}, Description: {policy.description}")

for task in tasks_data["tasks"]:
    user_id = task["assigned_to"]
    user_info = next((user for user in users_data["users"] if user["id"] == str(user_id)), {})
    user_name = user_info.get("name", "unknown")
    user_access_level = user_info.get("access_level", 0)
    action = task["actions"][0]["type"]
    resource = task["actions"][0]["resource_id"]
    resource_access_level = get_resource_access_level(resource)

    # Custom access level check
    logging.info(f"Checking custom access levels: User {user_name} (access level {user_access_level}) vs Resource {resource} (required access level {resource_access_level})")
    if user_access_level < resource_access_level:
        result = False
        logging.info(f"Custom check failed: User {user_name} with access level {user_access_level} denied access to {resource} requiring level {resource_access_level}")
    else:
        inquiry = Inquiry(action=action, resource=resource, subject={'name': user_name, 'access_level': user_access_level})
        logging.info(f"Creating inquiry: {inquiry}")
        result = guard.is_allowed(inquiry)
        logging.info(f"Inquiry result: {'allowed' if result else 'denied'}")

    log_event(user_name, resource, action, "allowed" if result else "denied")

    if result:
        logging.info(f"Inquiry allowed: User: {user_name}, Resource: {resource}, Action: {action}")
    else:
        logging.info(f"Inquiry denied: User: {user_name}, Resource: {resource}, Action: {action}")
        logging.info(f"Inquiry details: {Inquiry}")
        logging.info(f"Policies in storage:")
        log_policies(storage)

    update_task_result(task["id"], result)

with open('config/tasks.json', 'w') as file:
    json.dump(tasks_data, file, indent=4)

class VaktServer(ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, ps: PolicyStore, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.pip = MemoryStorage()
        self.pdp = LogGuard(self.pip, RulesChecker())

        policies = [policy_to_vakt(p) for p in ps.policies]
        for p in policies:
            self.pip.add(p)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.pdp.close()
        self.server_close()
