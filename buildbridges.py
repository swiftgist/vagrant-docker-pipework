#!/usr/bin/python

import yaml
import pprint
import re
from subprocess import Popen, PIPE

class Containers:
    def __init__(self, config):
        self.config = config
        pprint.pprint(config)
        self.containers = {}
        proc = Popen(['docker', 'ps'], stdout=PIPE)
        r = re.compile('^CONTAINER')
        for line in proc.stdout:
            if r.match(line):
                continue
            last_column = line[128:-2]
            pre, host, post = line.split('_')
            id = line[0:12]
            self.containers[host] = id

    PIPEWORK = "/usr/local/bin/pipework"
    def pipework(self):
        pprint.pprint(self.config)
        for server in self.config['servers'].keys():
            for bridge in self.config['bridges'].keys():
                if (bridge in self.config['servers'][server] and
                        self.config['servers'][server][bridge] == False):
                    continue
                if server in self.containers:
                    cmd = [ "sudo", self.PIPEWORK, "br_" + bridge, "-i", self.config['bridges'][bridge]['device'],  self.containers[server], self.config['bridges'][bridge]['base'] + "." + str(self.config['servers'][server]['octet']) +"/24" ]
                    print cmd
                    proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
                    for line in proc.stdout:
                        print line
                    for line in proc.stderr:
                        print line
                        r = re.compile('RTNETLINK answers: File exists')
                        if not (proc.returncode == 0 or r.match(line)):
                            exit

def main():
    with open('topology.yml', 'r') as f:
        config = yaml.load(f)
    pprint.pprint(config)
    c = Containers(config) 
    #pprint.pprint(c.containers)
    c.pipework()

# Main
if __name__ == "__main__":
    main()
