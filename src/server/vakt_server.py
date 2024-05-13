import logging
import json
from vakt import Policy, Guard, RulesChecker, rules, Inquiry
from vakt.storage.memory import MemoryStorage
from socketserver import BaseRequestHandler, ThreadingTCPServer
from vakt_util import log_event, update_task_result

# Load policies
with open('config/policies.json', 'r') as file:
    policies_data = json.load(file)

# Configure logging
logging.basicConfig(filename='app.log', level=logging.DEBUG, format='%(asctime)s - %(message)s')

class LogGuard(Guard):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class VaktHandler(BaseRequestHandler):
    def handle(self):
        res = self.request.recv(512)
        print(res)

# Create storage and add policies
storage = MemoryStorage()
checker = RulesChecker()

for policy_data in policies_data:
    subjects = policy_data.get('subject', {})
    if 'access_level' in subjects:
        subjects['access_level'] = rules.GreaterOrEqual(subjects['access_level']['geq'])

    policy = Policy(
        uid=policy_data['id'],
        description=policy_data.get('description', ''),
        effect=policy_data.get('effect', 'deny'),  # default to 'deny' if effect is not specified
        subjects=subjects,
        actions=[rules.Eq(action) for action in policy_data.get('action', {}).values()],  # Changed from 'actions' to 'action'
        resources=[rules.Eq(resource) for resource in policy_data.get('resource', {}).values()],  # Changed from 'resources' to 'resource'
        context=policy_data.get('context', {})
    )
    logging.info(f"Adding policy: {policy}")
    storage.add(policy)

# Log the policies in storage
policies_in_storage = list(storage.get_all(limit=100, offset=0))
logging.debug(f"Policies in storage: {policies_in_storage}")

# Create the Guard object with storage and checker
guard = Guard(storage, checker)

# Load tasks
with open('config/tasks.json', 'r') as file:
    tasks_data = json.load(file)

# Load users
with open('config/users.json', 'r') as file:
    users_data = json.load(file)

def get_user_access_level(user_id):
    for user in users_data['users']:
        if user['id'] == user_id:
            return user.get('access_level', 0)
    return 0

def get_policy_access_level(guard, resource_id):
    # Retrieve the policies related to the resource
    policies = [policy for policy in guard.storage.get_all(limit=100, offset=0) if policy.resources['id'] == resource_id]
    if policies:
        # Assume all policies for a resource have the same access_level requirement
        policy_access_level = policies[0].subjects['access_level']
        return policy_access_level
    return None

# Custom access level check function
def check_access(task, guard):
    user_id = task["assigned_to"]
    user_name = next((user['name'] for user in users_data['users'] if user['id'] == user_id), "Unknown")
    user_access_level = get_user_access_level(user_id)

    for action in task["actions"]:
        resource_id = action["resource_id"]
        resource = action["resource"]
        action_type = action["type"]

        logging.info(f"Checking custom access levels: User {user_name} (access level {user_access_level}) for Resource {resource_id} of type {resource}")

        # Retrieve policy access level from the guard
        policy_access_level = get_policy_access_level(guard, resource_id)
        logging.info(f"Policy access level required: {policy_access_level}")

        # Compare access levels using Vakt's rule directly
        if policy_access_level and policy_access_level.satisfied(user_access_level, {}):
            inquiry = Inquiry(action=action_type, resource=resource_id, subject={'name': user_name, 'access_level': user_access_level})
            logging.info(f"Creating inquiry: {inquiry}")

            # Log the inquiry object
            logging.debug(f"Inquiry object: {inquiry}")

            # Check access levels using guard
            result = guard.is_allowed(inquiry)
            logging.debug(f'Inquiry result: {result}')

            if result:
                logging.info(f"Inquiry allowed: User: {user_name}, Resource: {resource_id}, Action: {action_type}")
            else:
                logging.info(f"Inquiry denied: User: {user_name}, Resource: {resource_id}, Action: {action_type}")

            # Log event and update task result
            log_event(user_name, resource_id, action_type, "allowed" if result else "denied")
            update_task_result(task["id"], result)
        else:
            logging.info(f"Access denied for User: {user_name} due to insufficient access level")

# Check access for each task
for task in tasks_data['tasks']:
    check_access(task, guard)

# Save the updated tasks
with open('config/tasks.json', 'w') as file:
    json.dump(tasks_data, file, indent=4)

class VaktServer(ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, ps, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pip = MemoryStorage()
        self.pdp = LogGuard(self.pip, RulesChecker())

        policies = [Policy(
            uid=p['id'],
            description=p.get('description', ''),
            effect=p.get('effect', 'deny'),  # default to 'deny' if effect is not specified
            subjects=p.get('subject', {}),
            actions=p.get('action', {}),
            resources=p.get('resource', {}),
            context=p.get('context', {})
        ) for p in ps]
        
        for p in policies:
            self.pip.add(p)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.pdp.close()
        self.server_close()
