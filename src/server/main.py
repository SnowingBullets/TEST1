import json
import csv
import logging
import wx
import json
import os
from argparse import ArgumentParser
from collections import namedtuple
from vakt_server import VaktServer, VaktHandler
from vakt import Policy, Inquiry, Guard, RulesChecker, MemoryStorage

# Configure logging to write to app.log
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')

# Define a namedtuple for Policies
Policy = namedtuple('Policy', ['id', 'effect', 'resource', 'action', 'subject', 'context'])

def load_resources():
    with open('config/resources.json', 'r') as file:
        data = json.load(file)
        return data['resources']

def load_policies():
    with open('config/policies.json', 'r') as file:
        return json.load(file)

resources = load_resources()
policies = load_policies()

def load_policies_from_config(config_dir):
    policies = []
    for filename in os.listdir(config_dir):
        if filename.endswith(".json"):
            with open(os.path.join(config_dir, filename), 'r') as file:
                config = json.load(file)
                policy = Policy(
                    config['id'],
                    actions=config['actions'],
                    resources=config['resources'],
                    subjects=config['subjects'],
                    effect=config['effect'],
                    context=config.get('context', {}),
                    description=config.get('description', "")
                )
                policies.append(policy)
                logging.info(f"Added Policy: {policy}")
    return policies

def load_inquiries_from_csv(csv_file):
    inquiries = []
    with open(csv_file, newline='') as file:
        reader = csv.DictReader(file)
        for row in reader:
            context_str = row['Conditions'].replace('""', '"')
            try:
                context = json.loads(context_str)
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding JSON for row: {row}, error: {e}")
                context = {}

            inquiry = Inquiry(
                action=row['Action Type'],
                resource=row['Resource'],
                subject=row['User Name'],
                context=context
            )
            inquiries.append(inquiry)
    return inquiries

def process_tasks_to_csv():
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
                    'description': task['description'],
                    'assigned_to': task['assigned_to'],
                    'action_type': action['type'],
                    'resource': action['resource'],
                    'attributes': attributes,
                    'conditions': conditions,
                    'expected_outcome': action['expected_outcome']
                })
    wx.MessageBox('Tasks processed and saved to data.csv', 'Success', wx.OK | wx.ICON_INFORMATION)
    

class ActionInputFrame(wx.Dialog):
    def __init__(self, parent):
        super(ActionInputFrame, self).__init__(parent, title="Add Action", size=(400, 400))
        self.parent = parent
        self.InitUI()

    def InitUI(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Resource selection
        self.cb_resource = wx.ComboBox(panel, choices=[res['id'] for res in resources], style=wx.CB_READONLY)
        self.cb_resource.Bind(wx.EVT_COMBOBOX, self.on_resource_select)
        
        self.tc_type = wx.TextCtrl(panel)
        self.tc_attributes = wx.TextCtrl(panel)
        self.tc_expected_outcome = wx.TextCtrl(panel)
        save_button = wx.Button(panel, label='Save Action')
        save_button.Bind(wx.EVT_BUTTON, self.on_save_action)
        
        fields = [('Resource ID', self.cb_resource), ('Type', self.tc_type), ('Attributes (JSON)', self.tc_attributes), ('Expected Outcome', self.tc_expected_outcome)]
        for label, control in fields:
            vbox.Add(wx.StaticText(panel, label=label), flag=wx.EXPAND|wx.LEFT|wx.TOP, border=10)
            vbox.Add(control, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)
        
        vbox.Add(save_button, flag=wx.ALIGN_CENTER|wx.TOP, border=10)
        panel.SetSizer(vbox)

    def on_resource_select(self, event):
        # Get the selected resource details and fill the fields automatically
        selected_index = self.cb_resource.GetSelection()
        selected_resource = resources[selected_index]
        self.tc_type.SetValue('')  # Clear type field or set a default value
        self.tc_attributes.SetValue(json.dumps(selected_resource['attributes']))
        self.tc_expected_outcome.SetValue(selected_resource.get('expected_outcome', ''))
        
    def on_save_action(self, event):
        selected_resource = resources[self.cb_resource.GetSelection()]
        action_data = {
            'resource_id': selected_resource['id'],
            'resource': selected_resource['category'],  # Assuming 'category' is relevant here
            'type': self.tc_type.GetValue(),
            'attributes': json.loads(self.tc_attributes.GetValue()),
            'expected_outcome': self.tc_expected_outcome.GetValue()
        }
        self.parent.actions.append(action_data)
        self.Close()

class TaskInputFrame(wx.Frame):
    def __init__(self, parent, title):
        super(TaskInputFrame, self).__init__(parent, title=title, size=(450, 600))
        self.actions = []
        self.InitUI()

    def InitUI(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.tc_task_id = wx.TextCtrl(panel)
        self.cb_policy_id = wx.ComboBox(panel, choices=[policy['id'] for policy in policies], style=wx.CB_READONLY)
        self.tc_description = wx.TextCtrl(panel)
        self.tc_assigned_to = wx.TextCtrl(panel)
        add_button = wx.Button(panel, label='Add Task')
        add_action_button = wx.Button(panel, label='Add Action')
        process_tasks_button = wx.Button(panel, label='Process Tasks')  # New button for processing tasks
        
        add_button.Bind(wx.EVT_BUTTON, self.on_add_task)
        add_action_button.Bind(wx.EVT_BUTTON, self.on_add_action)
        process_tasks_button.Bind(wx.EVT_BUTTON, self.on_process_tasks)  # Bind the new button to handler

        fields = [
            ('Task ID', self.tc_task_id), ('Policy ID', self.cb_policy_id),
            ('Description', self.tc_description), ('Assigned To', self.tc_assigned_to)
        ]
        for label, control in fields:
            vbox.Add(wx.StaticText(panel, label=label), flag=wx.EXPAND|wx.LEFT|wx.TOP, border=10)
            vbox.Add(control, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        vbox.Add(add_action_button, flag=wx.EXPAND|wx.ALL, border=10)
        vbox.Add(add_button, flag=wx.ALIGN_CENTER|wx.ALL, border=10)
        vbox.Add(process_tasks_button, flag=wx.ALIGN_CENTER|wx.ALL, border=10)  # Add the new button to the layout
        panel.SetSizer(vbox)

    def on_add_task(self, event):
        selected_policy = policies[self.cb_policy_id.GetSelection()]
        task_data = {
            'id': self.tc_task_id.GetValue(),
            'policy_id': selected_policy['id'],
            'description': self.tc_description.GetValue(),
            'assigned_to': self.tc_assigned_to.GetValue(),
            'actions': self.actions
        }
        self.save_task(task_data)
        self.actions = []  # Reset actions list after saving
        wx.MessageBox('Task added with actions', 'Info', wx.OK | wx.ICON_INFORMATION)

    def on_add_action(self, event):
        action_frame = ActionInputFrame(self)
        action_frame.ShowModal()

    def on_process_tasks(self, event):
        # Function to process tasks to CSV
        process_tasks_to_csv()

    def save_task(self, task_data):
        try:
            with open('config/tasks.json', 'r+') as file:
                data = json.load(file)
                data['tasks'].append(task_data)
                file.seek(0)
                file.truncate()
                json.dump(data, file, indent=4)
            wx.MessageBox('Task successfully saved!', 'Success', wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            wx.LogError("Failed to save task: {}".format(str(e)))
            wx.MessageBox('Failed to save task: {}'.format(str(e)), 'Error', wx.OK | wx.ICON_ERROR)
                


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
                    
    def main():
        logging.info("Starting to process tasks...")

        # Initialize storage and guard
        storage = MemoryStorage()
        policies = load_policies_from_config('config')
        for policy in policies:
            storage.add(policy)
        
        guard = Guard(storage, RulesChecker())

        # Process access requests from CSV
        inquiries = load_inquiries_from_csv('config/data.csv')
        for inquiry in inquiries:
            if guard.is_allowed(inquiry):
                logging.info(f"Access granted: {inquiry}")
            else:
                logging.info(f"Access denied: {inquiry}")

if __name__ == "__main__":
    app = wx.App(False)
    frame = TaskInputFrame(None, title='Task Input Interface')
    frame.Show()
    app.MainLoop()
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