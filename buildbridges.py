#!/usr/bin/python

import yaml
import pprint
import re
import os.path
from subprocess import Popen, PIPE

def popen(cmd):
    """
    Execute a command, print both stdout and stderr, and exit unless 
    successful.
 
        cmd - a string of the command

    """
    proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
    for line in proc.stdout:
        print line
    for line in proc.stderr:
        print line
    if (proc.returncode != 0):
        exit

class Containers:
    """
    Docker uses LXC (i.e. Linux Containers).  These containers represent each 
    machine that needs one or more bridges.
    
    Example:
   
      initialize(config)
      pipework
      build

    Attributes:
        config: hash of bridges and servers
        containers: The mapping of container hostnames to container ids

    """
    def __init__(self, config):
        """
        The result of a 'docker ps' command is parsed and saved into a hash.
        """
        self.config = config
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
    """
    The pathname of the pipework shell script.
    """
    def pipework(self):
        """
        The simple implementation of calling the pipework script directly for the
        creation of all bridges in all containers.  Each command is composed and
        executed via popen3.  Success or a "File exists" result allows the 
        method to continue.  Any other result will be exit the program.
        """
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
        """
        The second implementation to call only the necessary commands to create 
        the bridge interfaces.  Each container creates a Bridges collection and
        then builds the interfaces.
        """
        for container in self.containers.keys():
            #b = Bridges(self.config['bridges'], self.containers[container])
            b = Bridges(self.config, container, self.containers[container])
            b.build()

class Bridges:
    """
    The representation of all bridges in a container.
    """
    def __init__(self, config, container, container_id):
        """
        A collection of all bridges with their interface names and base IPv4
        prefix.  Each bridge is created and saved in an array.  Virtual ethernet
        pairs are also created and saved in a hash. 
     
            all_bridges - a hash of bridge names and associated settings
            container_id - 12 character identity of a docker container

        """
        self.bridges = []
        self.veth = {}
        for bridge_name in config['bridges'].keys():
            self.bridges.append(Bridge(bridge_name, config['bridges'][bridge_name])) 
            self.veth[bridge_name] = Veth(config['servers'][container]['octet'], container_id, bridge_name, config['bridges'][bridge_name])
    def build(self):
        """
        Cycle through each bridge and verify whether it exists.  If not, add the
        the bridge and bring the interface up on the host machine.  Afterwards,
        create the virtual ethernet pair between the host and guest container.
        """
        for bridge in self.bridges:
            if not bridge.exists:
                bridge.add
                bridge.up
            self.veth[bridge.name].mtu = bridge.mtu()
            self.veth[bridge.name].symlink()
            if (self.veth[bridge.name].add()):
                self.veth[bridge.name].set()
                self.veth[bridge.name].up()
                self.veth[bridge.name].link()
                self.veth[bridge.name].netns_link()
                self.veth[bridge.name].netns_up()
                self.veth[bridge.name].netns_add()
                self.veth[bridge.name].netns_arp()

class Bridge:
    """
    Call command line tools for managing bridge interfaces.  All commands are
    called via sudo since root access is required and sudo is widely understood.

    """
    def __init__(self, name, bridge):
        """
        Creates an individual bridge interface.  
     
            name - The interface name such as br0 or management.
            settings - A hash of bridge settings
        """
        self.name = name
        self.device = bridge['device']
        self.base = bridge['base']
    def add(self):
        """
        Print the command and add the bridge interface
        """
        cmd = [ "sudo", "ip", "link", "add", "dev", self.name, "type", "base" ]
        print " ".join(cmd)
        popen(cmd)
    def up(self):
        """
        Print the command and enable the bridge interface
        """
        cmd = [ "sudo", "ip", "link", "set", self.name, "up" ]
        print " ".join(cmd)
        popen(cmd)
    def mtu(self):
        """
        Print the command and return the mtu value for the bridge interface
        """
        cmd = [ "sudo", "ip", "link", "show", self.name ]
        print " ".join(cmd)
        proc = Popen(cmd, stdout=PIPE)
        for line in proc.stdout:
            r = re.search('mtu (\d+)', line)
            return(r.group(1))
    def exists(self):
        """
        Check the existence of the bridge pathname in /sys/class/net.
        """
        return(os.path.isfile("/sys/class/net/" + self.name))

class Veth:
    """
    Virtual ethernet pairs
    """
    def __init__(self, octet, container_id, bridge_name, settings):
        """
        Generate the local and guest interface names based on guest device and
        container process id.  Capture all parameters and initialize mtu to nil.
     
            container_id = 12 character identifier for a Docker container
            bridge_name - The name of the bridge
            settings - The bridge settings
        """
        self.container_id = container_id
        self.bridge_name = bridge_name
        self.docker_pid = self.dockerpid()
        self.container_ifname = settings['device']
        self.address = settings['base'] + "." + str(octet)
        self.local_ifname = "v" + self.container_ifname + "pl" + self.docker_pid
        self.guest_ifname = "v" + self.container_ifname + "pg" + self.docker_pid
        self.mtu = None
    def dockerpid(self):
        """
        Finds the process id for a specific Docker container
        """
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
        """
        The mtu is necessary for adding veth peers and matches the bridge mtu
        """
        self.mtu = mtu
    def symlink(self):
        """
        Prints command and recreate symlink from /proc to /var/run
        """
        symlink_path = "/var/run/netns/" + self.docker_pid
        cmd = ["sudo", "rm", "-f", "name", symlink_path]
        print " ".join(cmd)
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        for line in proc.stdout:
            print line
        for line in proc.stderr:
            print line

        cmd = ["sudo", "ln", "-s", "/proc/" + self.docker_pid + "/ns/net", symlink_path]
        print " ".join(cmd)
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        for line in proc.stdout:
            print line
        for line in proc.stderr:
            print line

    def add(self):
        """
        Prints command and add veth peers
        """
        cmd = ["sudo", "ip", "link", "add", "name", self.local_ifname, "mtu", self.mtu, "type", "veth", "peer", "name", self.guest_ifname, "mtu", self.mtu]
        print " ".join(cmd)
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        for line in proc.stdout:
            print line
        for line in proc.stderr:
            print line
            r = re.compile('RTNETLINK answers: File exists')
            if r.match(line):
                return(False) # already exists
        if (proc.returncode != 0):
            exit
        return(True)
    def set(self):
        """
        Prints command and assigns the bridge master device
        """
        cmd = ["sudo", "ip", "link", "set", self.local_ifname, "master", self.bridge_name]
        print " ".join(cmd)
        popen(cmd)
    def up(self):
        """
        Prints command and enables local interface
        """
        cmd = ["sudo", "ip", "link", "set", self.local_ifname, "up"]
        print " ".join(cmd)
        popen(cmd)
    def link(self):
        """
        Prints command and assigns guest interface to container process
        """
        cmd = ["sudo", "ip", "link", "set", self.guest_ifname, "netns", self.docker_pid]
        print " ".join(cmd)
        popen(cmd)
    def netns_link(self):
        """
        Prints command and sets the guest interface to the container interface 
        (i.e. bridge name on host) from within the network namespace of the guest.
        """
        cmd = ["sudo", "ip", "netns", "exec", self.docker_pid, "ip", "link", "set", self.guest_ifname, "name", self.container_ifname]
        print " ".join(cmd)
        popen(cmd)
    def netns_add(self):
        """
        Prints command and assigns address to interface
        """
        cmd = ["sudo", "ip", "netns", "exec", self.docker_pid, "ip", "addr", "add", self.address + "/24", "dev", self.container_ifname]
        print " ".join(cmd)
        popen(cmd)
    def netns_up(self):
        """
        Prints command and enables interface on guest
        """
        cmd = ["sudo", "ip", "netns", "exec", self.docker_pid, "ip", "link", "set", self.container_ifname, "up"]
        print " ".join(cmd)
        popen(cmd)
    def netns_arp(self):
        """
        Prints command and notifies bridge
        """
        cmd = ["sudo", "ip", "netns", "exec", self.docker_pid, "arping", "-c", "1", "-A", "-I", self.container_ifname, self.address]
        print " ".join(cmd)
        popen(cmd)

    #def popen(self, cmd):
    #    """
    #    Redundant
    #    """
    #    proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
    #    for line in proc.stdout:
    #        print line
    #    for line in proc.stderr:
    #        print line
    #    if (proc.returncode != 0):
    #        exit

def main():
    """
    Load the topolgy yaml file and call an implementation
    """
    with open('topology.yml', 'r') as f:
        config = yaml.load(f)
    c = Containers(config) 
    #c.pipework()
    c.build()

# Main
if __name__ == "__main__":
    main()
