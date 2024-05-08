from collections import namedtuple

Policy = namedtuple(
    'Policy', ['id', 'effect', 'resource', 'action', 'subject', 'context']
)


class PolicyStore:
  def __init__(self, policies: list[Policy]):
    self.policies = policies

  @classmethod
  def from_json(cls, definition: dict):
    policies = []
    for p in definition:
      policies.append(
          Policy(
              p['id'], p['effect'], p['resource'], p['action'], p['subject'],
              p.get('context', {})
          )
      )
    return cls(policies)