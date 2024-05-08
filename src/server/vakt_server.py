from policies import PolicyStore
from socketserver import BaseRequestHandler, ThreadingTCPServer
from vakt import Policy, Guard, MemoryStorage, RulesChecker
from vakt_util import policy_to_vakt


class LogGuard(Guard):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)


class VaktHandler(BaseRequestHandler):
  def handle(self):
    res = self.request.recv(512)
    print(res)


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