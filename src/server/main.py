import json
import csv
import logging
import wx
import subprocess
import sys
import threading
from argparse import ArgumentParser
from collections import namedtuple
from vakt import Policy
from vakt.rules.string import Equal
from vakt_server import VaktServer, VaktHandler

# Global variable for the interface process
interface_process = None

def start_interface():
    global interface_process
    if interface_process is None:
        interface_process = subprocess.Popen([sys.executable, 'src/server/interface.py'])
        print("Interface started.")
    else:
        print("Interface is already running.")

def stop_interface():
    global interface_process
    if interface_process is not None:
        interface_process.terminate()
        interface_process = None
        print("Interface stopped.")
    else:
        print("Interface is not running.")

def command_handler():
    print("Type 'start interface' to start the interface, 'stop interface' to stop the interface, or 'exit' to quit.")
    while True:
        command = input("Enter command: ").strip().lower()
        if command == 'start interface':
            start_interface()
        elif command == 'stop interface':
            stop_interface()
        elif command == 'exit':
            stop_interface()  # Ensure the interface is stopped before exiting
            break
        else:
            print("Unknown command.")

# Set up logging
logging.basicConfig(filename='app.log', level=logging.DEBUG, format='%(asctime)s:%(levelname)s:%(message)s')

# Define a namedtuple for Policies
Policy = namedtuple('Policy', ['id', 'effect', 'resource', 'action', 'subject', 'context'])

def load_resources():
    with open('config/resources.json', 'r') as file:
        data = json.load(file)
        logging.info('Loaded resources: %s', data['resources'])
        return data['resources']

def load_policies():
    with open('config/policies.json', 'r') as file:
        policies = json.load(file)
        logging.info('Loaded policies: %s', policies)
        return policies
    
def load_data_from_csv():
    logging.debug("Loading policies from config/policies.csv")
    policies = []
    with open('config/data.csv', 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            policies.append(row)
    return policies

resources = load_resources()
policies = load_policies()

def process_tasks_to_csv():
    logging.debug("Processing tasks to CSV")
    with open('config/tasks.json', 'r') as file:
        tasks = json.load(file)['tasks']
    with open('config/data.csv', 'w', newline='') as csvfile:
        fieldnames = ['task_id', 'policy_id', 'resource_id', 'description', 'assigned_to', 'action_type', 'resource', 'attributes', 'conditions', 'expected_outcome']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for task in tasks:
            for action in task.get('actions', []):
                # Flatten attributes and conditions for CSV output
                attributes = json.dumps(action.get('attributes', {}))
                conditions = json.dumps(action.get('conditions', {}))
                writer.writerow({
                    'task_id': task['id'],
                    'policy_id': task['policy_id'],
                    'resource_id': task.get('resource_id', 'N/A'),  # Provide a default value if key is missing
                    'description': task['description'],
                    'assigned_to': task['assigned_to'],
                    'action_type': action['type'],
                    'resource': action['resource'],
                    'attributes': attributes,
                    'conditions': conditions,
                    'expected_outcome': action['expected_outcome']
                })

def enforce_policies_from_csv():
    policies = load_data_from_csv()
    
    for action in policies:
        resource = action.get('resource', '')
        if not isinstance(resource, str):
            resource = str(resource)
        
        enforce_action(Equal(resource), action)

def enforce_action(resource, action):
    # Your policy enforcement logic here
    pass

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
            fieldnames = ['Task ID', 'User Name', 'Policy ID', 'Resource ID', 'Policy Effect', 'Action Type', 'Resource', 'Attributes', 'Conditions', 'Expected Outcome']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            
            for task in self.tasks:
                user = next((user for user in self.users if user['id'] == task['assigned_to']), None)
                user_name = user['name'] if user else 'Unknown User'
                
                policy = self.policy_store.get_policy(task['policy_id'])
                policy_effect = policy.effect if policy else 'No Policy Found'
                
                for action in task.get('actions', []):
                    attributes = json.dumps(action['attributes'])
                    
                    writer.writerow({
                        'Task ID': task['id'],
                        'User Name': user_name,
                        'Policy ID': task['policy_id'],
                        'Policy Effect': policy_effect,
                        'Action Type': action['type'],
                        'Resource': action['resource'],
                        'Attributes': attributes,
                        'Expected Outcome': action['expected_outcome']
                    })

def log_task_processing():
    logging.debug("Starting task processing")
    with open('config/tasks.json', 'r') as file:
        tasks = json.load(file)['tasks']
    for task in tasks:
        logging.debug(f"Processing task: {task['id']}")
        user_name = task['assigned_to']
        logging.debug(f"Assigned to: {user_name}")
        policy = policy_store.get_policy(task['policy_id'])
        policy_effect = policy.effect if policy else 'No Policy Found'
        logging.debug(f"Policy effect: {policy_effect}")
        for action in task.get('actions', []):
            attributes = json.dumps(action['attributes'])
            logging.debug(f"Action: {action['type']}, Attributes: {attributes}")

def start_vakt_server(policy_store, port):
    with VaktServer(policy_store, ('', port), VaktHandler) as vs:
        logging.debug("Starting Vakt server")
        vs.serve_forever()

if __name__ == "__main__":
    print("Main script running...")

    # Start wx.App in a separate thread
    def start_wx_app():
        app = wx.App(False)
        app.MainLoop()

    wx_thread = threading.Thread(target=start_wx_app)
    wx_thread.daemon = True
    wx_thread.start()

    # Start command handler in a separate thread
    command_thread = threading.Thread(target=command_handler)
    command_thread.daemon = True
    command_thread.start()

    # Parse arguments
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

    logging.debug("Processing tasks")
    client_controller.process_tasks()

    # Start Vakt server in the main thread
    start_vakt_server(policy_store, args.port)