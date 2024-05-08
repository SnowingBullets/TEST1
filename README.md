# Zero-Trust Access Control System
This program is designed to allow for selected attributes to be required for access through the network and allowing the creation of data to test the system settings.

## Policy file format
### List operators
* in, not-in, all-in, all-not-in, any-in, any-not-in
### Logic operators
* eq, neq, gt, lt, geq, leq
### Modifiers
* and, or, not, any, either
```json
"subject": {
  "name": {"neq": "john"},
  "task-force": {"in": ["alpha", "bravo", "charlie"]}
}
```
Assigning various requirements for access based upon IP range, password access, geolocation, device and  user access level. Both successful and unsuccessful connections are logged and stored in the doc folder under logs. Multifactor authentification is also able to be assigned as a requirement for access.
