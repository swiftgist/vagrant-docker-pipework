#!/usr/bin/ruby

require 'pp'
require 'open3'
require 'yaml'

module Buildable

  class Containers

    def initialize
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
    def pipework(config)
      config['servers'].keys.each do |server|
        config['bridges'].keys.each do |bridge|
          next unless @containers[server] #skip downed containers
          cmd = "sudo #{PIPEWORK} br_#{bridge} -i #{config['bridges'][bridge]['device']} #{@containers[server]} #{config['bridges'][bridge]['base']}.#{config['servers'][server]['octet']}/24"
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

  end

  #== Bridge
  #
  # Call command line tools for managing bridge interfaces
  class Bridge

    def initialize
    end

    def add
    end

    def active?
    end

  end

  #== Interface
  #
  # Manage veth pairs 
  class Interface

    def initialize
    end

    def add
    end

    def master
    end

    def up
    end

  end
end

#= Main
if $PROGRAM_NAME =~ /buildbridges.rb$/ then
  config = YAML.load_file("topology.yml")

  c = Buildable::Containers.new
  c.pipework(config)

end
