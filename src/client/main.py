from argparse import ArgumentParser
from socket import AF_INET, SOCK_STREAM, socket


if __name__ == "__main__":
  ap = ArgumentParser()
  
  # TODO: Move address+port to configuration files
  ap.add_argument('-a', '--address', default='localhost')
  ap.add_argument('-p', '--port', default=14602, type=int)
  
  args = ap.parse_args()

  with socket(AF_INET, SOCK_STREAM) as s:
    s.connect((args.address, args.port))
    s.send(bytes('Hello', 'utf-8'))