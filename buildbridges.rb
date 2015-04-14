#!/usr/bin/ruby

require 'pp'
require 'open3'
require 'yaml'

module Buildable

  class Containers
    attr_accessor :containers

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

    PIPEWORK="/usr/local/bin/pipework"
    #== Pipework
    #
    # Simpler implementation of calling external script directly
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

    def build
      @containers.keys.each do |container|
        b = Buildable::Bridges.new(@config['bridges'], @containers[container])
        b.build
      end
    end

  end

  #== Bridges
  #
  # 
  class Bridges

    def initialize(bridge_names, container_id)
      @bridges = []
      @veth = {}
      bridge_names.keys.each do |name|
        @bridges << Bridge.new(name, bridge_names[name])
        @veth[name] = Veth.new(container_id, name, bridge_names[name])
      end
      @container_id = container_id
    end

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

  #== Bridge
  #
  # Call command line tools for managing bridge interfaces
  class Bridge
    attr_accessor :name

    def initialize(name, bridge)
      @name = name
      @device = bridge['device']
      @base = bridge['base']
    end

    def add
      cmd = "sudo ip link add dev #{@name} type bridge"
      pp cmd
      popen(cmd)
    end

    def up
      cmd = "sudo ip link set #{@name} up"
      pp cmd
      popen(cmd)
    end

    def mtu
      cmd = "sudo ip link show #{@name}"
      pp cmd
      Open3.popen3(cmd) do |stdin, stdout, stderr, wait_thr|
        exit unless wait_thr.value.success?
        stdout.readlines.join.match(/mtu (\d+)/)[1]
      end
    end

    def exists?
      File.exists?("/sys/class/net/#{@name}")
    end

    def popen(cmd)
      Open3.popen3(cmd) do |stdin, stdout, stderr, wait_thr|
        puts stdout.readlines
        puts stderr.readlines
        exit unless wait_thr.value.success?
      end
    end

  end

  class Veth
    attr_writer :mtu

    def initialize(container_id, name, bridge_names)
      @container_id = container_id
      @name = name
      @docker_pid = dockerpid
      @container_ifname = bridge_names['device']
      @local_ifname = "v#{@container_ifname}pl#{@docker_pid}"
      @guest_ifname = "v#{@container_ifname}pg#{@docker_pid}"
      @mtu = nil
    end

    def dockerpid
      cmd = "docker inspect --format='{{ .State.Pid }}' #{@container_id}"
      Open3.popen3(cmd) do |stdin, stdout, stderr, wait_thr|
        puts stderr.readlines
        exit unless wait_thr.value.success?
        stdout.readlines.join.chomp
      end
    end

    def add
      cmd = "sudo ip link add name #{@local_ifname} mtu #{@mtu} type veth peer name #{@guest_ifname} mtu #{@mtu}"
      pp cmd
      popen(cmd)
    end

    def set
      cmd = "sudo ip link set #{@local_ifname} master #{@name}"
      pp cmd
      popen(cmd)
    end

    def up
      cmd = "sudo ip link set #{@local_ifname} up"
      pp cmd
      popen(cmd)

    end

    def link
      cmd = "sudo ip link set #{@guest_ifname} netns #{@docker_pid}"
      pp cmd
      popen(cmd)
    end

    def netns
      cmd = "sudo ip netns exec #{@docker_pid} ip link set #{@guest_ifname} name #{@container_ifname}"
      pp cmd
      popen(cmd)
    end

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
if $PROGRAM_NAME =~ /buildbridges.rb$/ then
  config = YAML.load_file("topology.yml")

  c = Buildable::Containers.new(config)
  #c.pipework
  c.build

end
