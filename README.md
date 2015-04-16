# vagrant-docker-pipework
Experimenting with docker network setup in Ruby and Python

## Premise
I want to try Ceph with a Vagrant/Docker setup on Opensuse.  However, Vagrant does not support private networks currently within Docker (as of 4/16/2015).  An alternative is the nicely polished script from https://github.com/jpetazzo/pipework.  

While I could make a simple hardcoded wrapper, I wanted something slightly easier to modify until Vagrant supports private networks for Docker.  I also wanted to understand Docker networking and am learning Python.  

I wrote two implementations in Ruby and Python.  The first simply calls the _pipework_ script for every bridge on every container.  The second calls the individual commands directly for creating the bridge, host and guest interfaces.  

The initial Vagrantfile and Dockerfile came from https://github.com/bubenkoff/vagrant-docker-example.

## Usage
Each script is standalone and reads the *topology.yml* in the current directory.  The contents are the network bridges desired and the list of servers.  Here is an excerpt:

<pre>
---

bridges:
  management: 
    device: eth1
    base: 192.168.1
  ...
servers:
  admin: 
    octet: 100
    cluster: false
  ...
</pre>


Note: Ceph monitors do not need a network interface to the cluster network.

First, start the containers:

`$ vagrant up`

Then, edit the topology.yml to your liking and run either script:

`$ ./buildbridges.rb`

`$ ./buildbridges.py`

Either script can be rerun without causing harm.

## Caveats
The scripts only create and enable interfaces.  Nothing is removed.  

I have only done minimal testing.

Test cases are missing.
