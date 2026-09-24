import argparse

from .serveur import servir

p = argparse.ArgumentParser(prog="societe", description="Simulation de société — interface web.")
p.add_argument("--port", type=int, default=8000)
p.add_argument("--hote", default="127.0.0.1")
a = p.parse_args()
servir(a.hote, a.port)
