from collections import namedtuple

ResourceCategory = namedtuple(
    'ResourceCategory', ['id', 'actions', 'attributes']
)

Resource = namedtuple('Resource', ['id', 'category', 'attributes'])


class ResourceStore:
  def __init__(self, categories, resources):
    self.categories = categories
    self.resources = resources

  @classmethod
  def from_json(cls, definition: dict):
    categories = []
    for c in definition['categories']:
      categories.append(
          ResourceCategory(c['id'], c['actions'], c.get('attributes', []))
      )
    resources = []
    for r in definition['resources']:
      # TODO: Make sure attributes match between resource & category
      resources.append(
          Resource(r['id'], r['category'], r.get('attributes', []))
      )
    return cls(categories, resources)
