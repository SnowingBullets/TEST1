import json
import csv
import logging
import wx
import json
from argparse import ArgumentParser
from collections import namedtuple
from vakt_server import VaktServer, VaktHandler

# Set up logging
logging.basicConfig(filename='app.log', level=logging.DEBUG, format='%(asctime)s:%(levelname)s:%(message)s')

# Define a namedtuple for Policies
Policy = namedtuple('Policy', ['id', 'effect', 'resource', 'action', 'subject', 'context'])

def process_tasks_to_csv():
    with open('config/tasks.json', 'r') as file:
        tasks = json.load(file)['tasks']
    with open('config/data.csv', 'w', newline='') as csvfile:
        fieldnames = ['task_id', 'policy_id', 'description', 'assigned_to', 'action_type', 'resource', 'attributes', 'conditions', 'expected_outcome']
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
        super(ActionInputFrame, self).__init__(parent, title="Add Action", size=(300, 300))
        self.parent = parent
        self.InitUI()

    def InitUI(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.tc_type = wx.TextCtrl(panel)
        self.tc_resource = wx.TextCtrl(panel)
        self.tc_attributes = wx.TextCtrl(panel)
        self.tc_conditions = wx.TextCtrl(panel)
        self.tc_expected_outcome = wx.TextCtrl(panel)
        save_button = wx.Button(panel, label='Save Action')
        save_button.Bind(wx.EVT_BUTTON, self.on_save_action)

        # Layout adjustments
        labels = ['Type', 'Resource', 'Attributes', 'Conditions', 'Expected Outcome']
        controls = [self.tc_type, self.tc_resource, self.tc_attributes, self.tc_conditions, self.tc_expected_outcome]
        for label, control in zip(labels, controls):
            vbox.Add(wx.StaticText(panel, label=label), flag=wx.EXPAND|wx.LEFT|wx.TOP, border=10)
            vbox.Add(control, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        vbox.Add(save_button, flag=wx.ALIGN_CENTER|wx.TOP, border=10)
        panel.SetSizer(vbox)

    def on_save_action(self, event):
        action_data = {
            'type': self.tc_type.GetValue(),
            'resource': self.tc_resource.GetValue(),
            'attributes': self.tc_attributes.GetValue(),
            'conditions': self.tc_conditions.GetValue(),
            'expected_outcome': self.tc_expected_outcome.GetValue()
        }
        self.parent.actions.append(action_data)
        self.Close()

class TaskInputFrame(wx.Frame):
    def __init__(self, parent, title):
        super(TaskInputFrame, self).__init__(parent, title=title, size=(450, 400))
        self.InitUI()
        self.SetMinSize((450, 400))  # Setting a minimum size to ensure all fields are visible

    def InitUI(self):
        panel = wx.Panel(self)
        grid = wx.GridBagSizer(5, 5)  # Using GridBagSizer for better control over layout

        # Labels and Text Controls for action details
        lbl_type = wx.StaticText(panel, label="Type")
        self.tc_type = wx.TextCtrl(panel)
        lbl_resource = wx.StaticText(panel, label="Resource")
        self.tc_resource = wx.TextCtrl(panel)
        lbl_attributes = wx.StaticText(panel, label="Attributes")
        self.tc_attributes = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 60))
        lbl_conditions = wx.StaticText(panel, label="Conditions")
        self.tc_conditions = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 60))
        lbl_outcome = wx.StaticText(panel, label="Expected Outcome")
        self.tc_expected_outcome = wx.TextCtrl(panel)
        save_button = wx.Button(panel, label='Save Action')
        save_button.Bind(wx.EVT_BUTTON, self.on_save_action)

        # Arranging items in the grid
        grid.Add(lbl_type, pos=(0, 0), flag=wx.LEFT|wx.TOP, border=10)
        grid.Add(self.tc_type, pos=(0, 1), span=(1, 2), flag=wx.EXPAND|wx.RIGHT|wx.TOP, border=10)
        grid.Add(lbl_resource, pos=(1, 0), flag=wx.LEFT|wx.TOP, border=10)
        grid.Add(self.tc_resource, pos=(1, 1), span=(1, 2), flag=wx.EXPAND|wx.RIGHT|wx.TOP, border=10)
        grid.Add(lbl_attributes, pos=(2, 0), flag=wx.LEFT|wx.TOP, border=10)
        grid.Add(self.tc_attributes, pos=(2, 1), span=(1, 2), flag=wx.EXPAND|wx.RIGHT|wx.TOP, border=10)
        grid.Add(lbl_conditions, pos=(3, 0), flag=wx.LEFT|wx.TOP, border=10)
        grid.Add(self.tc_conditions, pos=(3, 1), span=(1, 2), flag=wx.EXPAND|wx.RIGHT|wx.TOP, border=10)
        grid.Add(lbl_outcome, pos=(4, 0), flag=wx.LEFT|wx.TOP, border=10)
        grid.Add(self.tc_expected_outcome, pos=(4, 1), span=(1, 2), flag=wx.EXPAND|wx.RIGHT|wx.TOP, border=10)
        grid.Add(save_button, pos=(5, 0), span=(1, 3), flag=wx.EXPAND|wx.BOTTOM|wx.TOP, border=10)

        grid.AddGrowableCol(1)
        panel.SetSizer(grid)
        
    def on_save_action(self, event):
        action_data = {
            'type': self.tc_type.GetValue(),
            'resource': self.tc_resource.GetValue(),
            'attributes': self.tc_attributes.GetValue(),
            'conditions': self.tc_conditions.GetValue(),
            'expected_outcome': self.tc_expected_outcome.GetValue()
        }
        self.EndModal(wx.ID_OK)  # Close dialog and return OK status
        self.parent.actions.append(action_data)  # Append to parent's action list    
        
    def on_add_action(self, event):
        action_frame = ActionInputFrame(self)
        action_frame.ShowModal()

    def on_add_task(self, event):
        task_data = {
            'id': self.tc_task_id.GetValue(),
            'policy_id': self.tc_policy_id.GetValue(),
            'description': self.tc_description.GetValue(),
            'assigned_to': self.tc_assigned_to.GetValue(),
            'actions': self.actions
        }
        self.save_task(task_data)
        wx.MessageBox('Task added', 'Info', wx.OK | wx.ICON_INFORMATION)
        self.actions = []  # Reset actions list after saving

    def save_task(self, task_data):
        with open('config/tasks.json', 'r+') as file:
            data = json.load(file)
            data['tasks'].append(task_data)
            file.seek(0)
            file.truncate()
            json.dump(data, file, indent=4)
            


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
            fieldnames = ['Task ID', 'User Name', 'Policy ID', 'Policy Effect', 'Action Type', 'Resource', 'Attributes', 'Conditions', 'Expected Outcome']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            
            for task in self.tasks:
                user = next((user for user in self.users if user['id'] == task['assigned_to']), None)
                user_name = user['name'] if user else 'Unknown User'
                
                policy = self.policy_store.get_policy(task['policy_id'])
                policy_effect = policy.effect if policy else 'No Policy Found'
                
                for action in task.get('actions', []):
                    attributes = json.dumps(action['attributes'])
                    conditions = json.dumps(action['conditions'])
                    
                    writer.writerow({
                        'Task ID': task['id'],
                        'User Name': user_name,
                        'Policy ID': task['policy_id'],
                        'Policy Effect': policy_effect,
                        'Action Type': action['type'],
                        'Resource': action['resource'],
                        'Attributes': attributes,
                        'Conditions': conditions,
                        'Expected Outcome': action['expected_outcome']
                    })


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