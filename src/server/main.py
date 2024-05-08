import json
import csv
import logging
from argparse import ArgumentParser
from collections import namedtuple
from vakt_server import VaktServer, VaktHandler

# Set up logging
logging.basicConfig(filename='app.log', level=logging.DEBUG, format='%(asctime)s:%(levelname)s:%(message)s')

# Define a namedtuple for Policies
Policy = namedtuple('Policy', ['id', 'effect', 'resource', 'action', 'subject', 'context'])

class PolicyStore:
    def __init__(self, policies: list[Policy]):
        self.policies = policies

    @classmethod
    def from_json(cls, definition: list):
        policies = []
        for p in definition:
            try:
                policy = Policy(
                    p['id'],
                    p['effect'],
                    p['resource'],
                    p['action'],
                    p.get('subject', {}),
                    p.get('context', {})
                )
                policies.append(policy)
            except KeyError as e:
                logging.error(f"Missing key {e} in policy data: {p}")
                continue
        return cls(policies)

    def get_policy(self, policy_id):
        for policy in self.policies:
            if policy.id == policy_id:
                return policy
        logging.warning(f"No policy found with ID: {policy_id}")
        return None
      
class ClientController:
    def __init__(self, user_data, tasks, policy_store):
        self.users = user_data
        self.tasks = tasks
        self.policy_store = policy_store

    def process_tasks(self):
        logging.info("Starting to process tasks...")
        with open('config/data.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Task ID', 'User Name', 'Policy ID', 'Policy Effect'])

            for task in self.tasks:
                user = next((user for user in self.users if user['id'] == task['assigned_to']), None)
                if user:
                    user_name = user['name']
                else:
                    user_name = 'Unknown User'
                    logging.debug(f"No user matched for task ID {task['id']}")

                policy = self.policy_store.get_policy(task['policy_id'])
                if policy:
                    logging.debug(f"Processing task {task['id']} for user {user_name} under policy {policy.id}")
                    writer.writerow([task['id'], user_name, policy.id, policy.effect])
                else:
                    logging.debug(f"No policy found for task ID {task['id']}")
                    writer.writerow([task['id'], user_name, 'No Policy Found', 'N/A'])

if __name__ == "__main__":
    ap = ArgumentParser()
    ap.add_argument('-p', '--port', default=14602, type=int)
    ap.add_argument('--user', default='config/users.json', type=str, help='Path to the user json file')
    ap.add_argument('--task', default='config/tasks.json', type=str, help='Path to the tasks json file')
    ap.add_argument('--policy', default='config/policies.json', type=str, help='Path to the policies json file')
    
    args = ap.parse_args()

    with open(args.user, 'r') as f:
        user_data = json.load(f)['users']
    with open(args.task, 'r') as f:
        tasks = json.load(f)['tasks']
    with open(args.policy, 'r') as f:
        policies = json.load(f)
    
    policy_store = PolicyStore.from_json(policies)
    client_controller = ClientController(user_data, tasks, policy_store)

    client_controller.process_tasks()

    with VaktServer(policy_store, ('', args.port), VaktHandler) as vs:
        vs.serve_forever()
