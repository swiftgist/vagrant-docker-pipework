#!/usr/bin/ruby

require 'pp'
require 'open3'
require 'yaml'

# The namespace for holding Containers, Bridges and Bridge classes.
#
# Examples
#
#   Containers.new(config)
#   Bridges.new(all_bridge_details, container_id)
#   Bridge(name, bridge_details)
module Buildable

  # Docker uses LXC (i.e. Linux Containers).  These containers represent each 
  # machine that needs one or more bridges.
  # 
  # Examples
  #
  #   initialize(config)
  #   pipework
  #   build
  class Containers
    # The mapping of container hostnames to container ids
    attr_accessor :containers

    # The result of a +docker+ +ps+ command is parsed and saved into a hash.  
    # The entries map hostnames to container ids.  The config is also saved.
    #
    #   config - a hash of bridges and servers
    def initialize(config)
      @config = config
      @containers = {}
      Open3.popen3("docker ps") do |stdin, stdout, stderr, wait_thr|
        stdout.each_line do |line|
          next if line.match(/^CONTAINER/)
          # Omit newline from last column and extract hostname between underscores
          host = line.byteslice(128..-2).sub(/[^_]*_([^_]*)_.*/, '\1')
          id = line.byteslice(0, 12)
          @containers[host] = id
        end
      end
    end

    # A Constant for the pathname of the pipework shell script.
    PIPEWORK="/usr/local/bin/pipework"

    # The simple implementation of calling the pipework script directly for the
    # creation of all bridges in all containers.  Each command is composed and
    # executed via +popen3+.  Success or a "File exists" result allows the method
    # to continue.  Any other result will be exit the program.
    def pipework
      @config['servers'].keys.each do |server|
        @config['bridges'].keys.each do |bridge|
          next unless @containers[server] #skip downed containers

          # Skip bridges set to false for this container
          next if (@config['servers'][server].has_key?(bridge) and
              @config['servers'][server][bridge] == false) 

          cmd = "sudo #{PIPEWORK} br_#{bridge} -i #{@config['bridges'][bridge]['device']} #{@containers[server]} #{@config['bridges'][bridge]['base']}.#{@config['servers'][server]['octet']}/24"
          puts cmd
          Open3.popen3(cmd) do |stdin, stdout, stderr, wait_thr|
            puts stdout.readlines
            line = stderr.readlines.join
            puts line
            exit unless (wait_thr.value.success? or 
                         line.match(/RTNETLINK answers: File exists/))
          end
          puts
        end
      end
    end

    # The second implementation to call only the necessary commands to create the
    # bridge interfaces.  Each container creates a +Bridges+ collection and then
    # builds the interfaces.
    def build
      @containers.keys.each do |container|
        b = Buildable::Bridges.new(@config['bridges'], @containers[container])
        b.build
      end
    end

  end

  # The representation of all bridges in a container.
  class Bridges

    # A collection of all bridges with their interface names and base IPv4
    # prefix.  Each bridge is created and saved in an array.  Virtual ethernet
    # pairs are also created and saved in a hash. 
    #
    #   all_bridges - a hash of bridge names and associated settings
    #   container_id - 12 character identity of a docker container
    def initialize(all_bridges, container_id)
      @bridges = []
      @veth = {}
      all_bridges.keys.each do |name|
        @bridges << Bridge.new(name, all_bridges[name])
        @veth[name] = Veth.new(container_id, name, all_bridges[name])
      end
      @container_id = container_id
    end

    # Cycle through each bridge and verify whether it exists.  If not, add the
    # the bridge and bring the interface up on the host machine.  Afterwards,
    # create the virtual ethernet pair between the host and guest container.
    def build
      @bridges.each do |bridge|
        unless bridge.exists? then
          bridge.add
          bridge.up
        end
        @veth[bridge.name].mtu = bridge.mtu
        if @veth[bridge.name].add then
          @veth[bridge.name].set
          @veth[bridge.name].up
          @veth[bridge.name].link
          @veth[bridge.name].netns
        end

      end
    end
  end

  # Call command line tools for managing bridge interfaces.  All commands are
  # called via sudo since root access is required and sudo is widely understood.
  class Bridge
    # Name of the bridge
    attr_reader :name

    # Creates an individual bridge interface.  
    #
    #   name - The interface name such as br0 or management.
    #   settings - A hash of bridge settings
    def initialize(name, settings)
      @name = name
      @device = settings['device']
      @base = settings['base']
    end

    # Print the command and add the bridge interface
    def add
      cmd = "sudo ip link add dev #{@name} type bridge"
      pp cmd
      popen(cmd)
    end

    # Print the command and enable the bridge interface
    def up
      cmd = "sudo ip link set #{@name} up"
      pp cmd
      popen(cmd)
    end

    # Print the command and return the mtu value for the bridge interface
    def mtu
      cmd = "sudo ip link show #{@name}"
      pp cmd
      Open3.popen3(cmd) do |stdin, stdout, stderr, wait_thr|
        exit unless wait_thr.value.success?
        stdout.readlines.join.match(/mtu (\d+)/)[1]
      end
    end

    # Check the existence of the bridge pathname in /sys/class/net.
    def exists?
      File.exists?("/sys/class/net/#{@name}")
    end

    # Execute a command, print both stdout and stderr, and exit unless successful
    #
    #   cmd - a string of the command
    def popen(cmd)
      Open3.popen3(cmd) do |stdin, stdout, stderr, wait_thr|
        puts stdout.readlines
        puts stderr.readlines
        exit unless wait_thr.value.success?
      end
    end

  end

  # Virtual ethernet pairs
  class Veth
    # The mtu is necessary for adding veth peers and matches the bridge mtu
    attr_writer :mtu

    # Generate the local and guest interface names based on guest device and
    # container process id.  Capture all parameters and initialize mtu to nil.
    #
    #   container_id = 12 character identifier for a Docker container
    #   name - The name of the bridge
    #   settings - The bridge settings
    def initialize(container_id, name, settings)
      @container_id = container_id
      @name = name
      @docker_pid = dockerpid
      @container_ifname = settings['device']
      @local_ifname = "v#{@container_ifname}pl#{@docker_pid}"
      @guest_ifname = "v#{@container_ifname}pg#{@docker_pid}"
      @mtu = nil
    end

    # Finds the process id for a specific Docker container
    def dockerpid
      cmd = "docker inspect --format='{{ .State.Pid }}' #{@container_id}"
      Open3.popen3(cmd) do |stdin, stdout, stderr, wait_thr|
        puts stderr.readlines
        exit unless wait_thr.value.success?
        stdout.readlines.join.chomp
      end
    end

    # Prints command and add veth peers
    def add
      cmd = "sudo ip link add name #{@local_ifname} mtu #{@mtu} type veth peer name #{@guest_ifname} mtu #{@mtu}"
      pp cmd
      popen(cmd)
    end

    # Prints command and assigns the bridge master device
    def set
      cmd = "sudo ip link set #{@local_ifname} master #{@name}"
      pp cmd
      popen(cmd)
    end

    # Prints command and enables local interface
    def up
      cmd = "sudo ip link set #{@local_ifname} up"
      pp cmd
      popen(cmd)

    end

    # Prints command and assigns guest interface to container process
    def link
      cmd = "sudo ip link set #{@guest_ifname} netns #{@docker_pid}"
      pp cmd
      popen(cmd)
    end

    # Prints command and sets the guest interface to the container interface (i.e.
    # bridge name on host) from within the network namespace of the guest.
    def netns
      cmd = "sudo ip netns exec #{@docker_pid} ip link set #{@guest_ifname} name #{@container_ifname}"
      pp cmd
      popen(cmd)
    end

    # Redundant
    def popen(cmd)
      Open3.popen3(cmd) do |stdin, stdout, stderr, wait_thr|
        puts stdout.readlines
        line = stderr.readlines.join
        puts line
        wait_thr.value.success?
                    # line.match(/RTNETLINK answers: File exists/))
      end
    end

  end

end

#= Main
# Check if script is called directly.  Allows including in tests.
if $PROGRAM_NAME =~ /buildbridges.rb$/ then
  config = YAML.load_file("topology.yml")

  c = Buildable::Containers.new(config)
  #c.pipework
  c.build

end
