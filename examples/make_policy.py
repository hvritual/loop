"""Write an explicit fixture-only policy; register project-specific adapters for real work."""
import argparse
import json
from demo import example_policy
p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--docker-image")
args = p.parse_args()
print(json.dumps(example_policy("docker" if args.docker_image else "trusted", args.docker_image), indent=2))
