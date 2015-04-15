#!/usr/bin/python

import yaml
import pprint
import re
import os.path
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
                    print " ".join(cmd)
                    proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
                    for line in proc.stdout:
                        print line
                    for line in proc.stderr:
                        print line
                        r = re.compile('RTNETLINK answers: File exists')
                        if not (proc.returncode == 0 or r.match(line)):
                            exit
    def build(self):
        for container in self.containers.keys:
            print container
            b = Bridges(self.config['bridges'], self.containers[container])
            b.build

class Bridges:
    def __init__(self, bridge_names, container_id):
        self.bridges = []
        self.veth = {}
        for name in bridge_names.keys:
            self.bridges.append(Bridge(name, bridge_names[name])) 
            self.veth[name] = Veth(container_id, name, bridge_names[name])
    def build(self):
        for bridge in self.bridges:
            if not bridge.exists:
                bridge.add
                bridge.up
            self.veth[bridge.name].mtu = bridge.mtu
            if (self.veth[bridge.name].add):
                self.veth[bridge.name].set
                self.veth[bridge.name].up
                self.veth[bridge.name].link
                self.veth[bridge.name].netns

class Bridge:
    def __init__(self, name, bridge):
        self.name = name
        self.device = bridge['device']
        self.base = bridge['base']
    def add(self):
        cmd = [ "sudo", "ip", "link", "add", "dev", self.name, "type", "base" ]
        print " ".join(cmd)
        popen(cmd)
    def up(self):
        cmd = [ "sudo", "ip", "link", "set", self.name, "up" ]
        print " ".join(cmd)
        popen(cmd)
    def mtu(self):
        cmd = [ "sudo", "ip", "link", "show", self.name ]
        print " ".join(cmd)
        popen(cmd)
        proc = Popen(cmd, stdout=PIPE)
        r = re.compile('mtu (\d+)')
        for line in proc.stdout:
            r.match(line)
            return(r.group(0))
    def exists(self):
        return(os.path.isfile("/sys/class/net/" + self.name))
    def popen(self, cmd):
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        for line in proc.stdout:
            print line
        for line in proc.stderr:
            print line
        if (proc.returncode != 0):
            exit

class Veth:
    def __init__(self, container_id, name, bridge_names):
        self.container_id = container_id
        self.name = name
        self.docker_pid = dockerpid()
        self.container_ifname = bridge_names['device']
        self.local_ifname = "v" + self.container_ifname + "pl" + self.docker_pid
        self.guest_ifname = "v" + self.container_ifname + "pg" + self.docker_pid
        self.mtu = None
    def dockerpid(self):
        cmd = [ "docker", "inspect", "--format='{{ .State.Pid }}'", self.container_id ]
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        for line in proc.stderr:
            print line
        if (proc.returncode != 0):
            exit
        for line in proc.stdout:
            return(line.rstrip('\n'))
    @property
    def mtu(self):
        self.mtu
    @mtu.setter
    def mtu(self, mtu):
        self.mtu = mtu
    def add(self):
        cmd = ["sudo", "ip", "link", "add", "name", self.local_ifname, "mtu", self.mtu, "type", "veth", "peer", "name", self.guest_ifname, "mtu", self.mtu]
        print " ".join(cmd)
        popen(cmd)
    def set(self):
        cmd = ["sudo", "ip", "link", "set", self.local_ifname, "up"]
        print " ".join(cmd)
        popen(cmd)
    def set(self):
        cmd = ["sudo", "ip", "link", "set", self.guest_ifname, "netns", self.docker_pid]
        print " ".join(cmd)
        popen(cmd)
    def netns(self):
        cmd = ["sudo", "ip", "netns", "exec", self.docker_pid, "ip", "link", "set", self.guest_ifname, "name", self.container_ifname]
        print " ".join(cmd)
        popen(cmd)
    def popen(self, cmd):
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        for line in proc.stdout:
            print line
        for line in proc.stderr:
            print line
        if (proc.returncode != 0):
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
