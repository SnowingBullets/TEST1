import json
import csv
import logging
import wx
from collections import namedtuple


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
    
def load_policies_from_csv():
    logging.debug("Loading policies from config/policies.csv")
    policies = []
    with open('config/policies.csv', 'r') as csvfile:
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
            
if __name__ == "__main__":
    logging.debug("Starting application")
    app = wx.App(False)
    frame = TaskInputFrame(None, title='Task Input Interface')
    frame.Show()
    app.MainLoop()