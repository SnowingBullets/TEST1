import logging
import json
from policies import PolicyStore
from vakt import Policy, Inquiry, Guard, RulesChecker
from vakt.storage.memory import MemoryStorage
from socketserver import BaseRequestHandler, ThreadingTCPServer
from vakt_util import log_event, policy_to_vakt, update_task_result

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

def log_policies(storage):
    policies = storage.get_all(limit=100, offset=0)
    for policy in policies:
        logging.info(f"Policy ID: {policy.uid}, Effect: {policy.effect}, Description: {policy.description}")

for task in tasks_data["tasks"]:
    user_id = task["assigned_to"]
    user_name = next((user["name"] for user in users_data["users"] if user["id"] == str(user_id)), "unknown")
    action = task["actions"][0]["type"]
    resource = task["actions"][0]["resource_id"]

    inquiry = Inquiry(action=action, resource=resource, subject={'name': user_name})
    result = guard.is_allowed(inquiry)

    log_event(user_name, resource, action, "allowed" if result else "denied")

    if result:
        logging.info(f"Inquiry allowed: User: {user_name}, Resource: {resource}, Action: {action}")
    else:
        logging.info(f"Inquiry denied: User: {user_name}, Resource: {resource}, Action: {action}")
        logging.info(f"Inquiry details: {inquiry}")
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
