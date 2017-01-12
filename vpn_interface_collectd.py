#!/usr/bin/env python
# coding=utf-8

import subprocess
import socket
import os
import traceback
import time
import datetime
import copy


class CmdError(Exception):
    pass


def get_host_name():
    return socket.gethostname().replace("-", "_")


def get_host_ip():
    host_file = os.popen('ifconfig eth0 | grep "inet\ addr" | cut -d: -f2 | cut -d" " -f1')
    host_ip = host_file.read()
    host_ip = host_ip.strip()
    return host_ip


def get_time():
    return time.time()


class IfconfigStatus(object):
    interfaces = ['eth0', 'eth2']

    def get_all_interface_stats(self):
        stat_dict = {}
        for interface in self.interfaces:
            stat_dict[interface] = self._get_interface_status(interface)
        return stat_dict

    def _get_interface_status(self, interface):
        cmd = self._compose_command(interface)
        output = self._run(cmd)
        rx_bytes = None
        tx_bytes = None
        for line in output:
            if 'RX bytes:' in line:
                rx_bytes = int(line.split('RX bytes:')[1].split(' ')[0].strip())
                tx_bytes = int(line.split('TX bytes:')[1].split(' ')[0].strip())
                current_time = get_time()
        return [rx_bytes, tx_bytes, int(current_time)]

    def _compose_command(self, interface):
        cmd = "sudo ifconfig %s" % interface
        return cmd

    def _run(self, cmd):
        try:
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, close_fds=True)
            (stdout, stderr) = proc.communicate()
            output = stdout.split("\n")
            #            print("cmd %s output is %s" % (cmd, output))
            result = []
            for line in output:
                if 'RX bytes' in line:
                    result.append(line)
            if result is None:
                raise CmdError("failed to execute command %s, outputis %s" % (cmd, output))
            return result
        except Exception as err:
            raise CmdError("failed to execute command: %s, reason: %s" % (' '.join(cmd), err.message))


class VPNInterfaceMon(object):
    def __init__(self):
        self.plugin_name = "vpn_interface_stat"
        self.interval = 5
        self.hostname = get_host_name()
        self.verbose_logging = False
        self.hostip = get_host_ip()
        self.interfaces = ['eth0', 'eth2']
        self.BASE = IfconfigStatus().get_all_interface_stats()

    def log_verbose(self, msg):
        if not self.verbose_logging:
            return collectd.info('%s plugin [verbose]: %s' % (self.plugin_name, msg))

    def get_rate(self, delta, interva):
        return delta / interva

    #    def BASE_TIME(self):
    #        time.sleep(1)

    def configure_callback(self, conf):
        for node in conf.children:
            val = str(node.values[0])
            if node.key == 'Verbose':
                self.verbose_logging = val in ['True', 'true']
            elif node.key == "PluginName":
                self.plugin_name = val
            else:
                collectd.warning('[plugin] %s: unknown config key: %s' % (self.plugin_name, node.key))

    def dispatch_value(self, plugin_instance, plugin, host, type, type_instance, value):
        #       self.log_verbose("Dispatching value plugin_instance=%s,plugin=%s, host=%s, type=%s, type_instance=%s, value=%s" %
        #                       (plugin_instance,plugin, host, type, type_instance, value))
        val = collectd.Values(type=type)
        val.plugin = plugin
        val.host = host
        val.type_instance = type_instance
        val.plugin_instance = plugin_instance
        # val.values = [value]
        val.values = [value]
        val.dispatch()
        self.log_verbose("Dispatched value plugin_instance=%s,plugin=%s, host=%s, type=%s, type_instance=%s, value=%s" %
                         (plugin_instance, plugin, host, type, type_instance, value))

    def get_delta_dict(self, latest_dict):
        delta_dict = {}
        rate_dict = {}
        # self.log_verbose(self.BASE)
        # self.log_verbose(latest_dict)
        for key, values in latest_dict.iteritems():
            org_value = self.BASE.get(key)
            delta_rx_bytes = values[0] - org_value[0]
            delta_tx_bytes = values[1] - org_value[1]
            interva = values[2] - org_value[2]
            delta_dict[key] = [delta_rx_bytes, delta_tx_bytes]
            self.BASE[key] = values
            rate_dict[key] = [int(delta_rx_bytes / interva), int(delta_tx_bytes / interva)]
        # {"eth0":[rx_bytes, tx_bytes], }
        return rate_dict

    def read_callback(self):
        try:
            #            self.log_verbose("plugin %s read callback called, process is: %s" % (self.plugin_name, self.interfaces))

            interface_status = IfconfigStatus()
            interface_stat = interface_status.get_all_interface_stats()
            host = self.hostip
            for interface, value in interface_stat.iteritems():
                type_instance = interface
                plugin_instance = "WuXi_site"
                # {"eth0":[rx_bytes, tx_bytes, rx_dropped, tx_dropped, rx_errors, tx_errors], }
                self.dispatch_value(plugin_instance, self.plugin_name, host, "rx_bytes", type_instance, value[0])
                self.dispatch_value(plugin_instance, self.plugin_name, host, "tx_bytes", type_instance, value[1])
            delta_status = self.get_delta_dict(interface_stat)
            for interface, value in delta_status.iteritems():
                type_instance = interface
                plugin_instance = "Wuxi_site"
                self.dispatch_value(plugin_instance, self.plugin_name, host, "rx_rate", type_instance, value[0])
                self.dispatch_value(plugin_instance, self.plugin_name, host, "tx_rate", type_instance, value[1])

        except Exception as exp:
            self.log_verbose(traceback.print_exc())
            self.log_verbose("plugin %s run into exception" % (self.plugin_name))
            self.log_verbose(exp.message)


if __name__ == '__main__':

    vpn_status = VPNInterfaceMon()

else:
    import collectd

    vpn_status = VPNInterfaceMon()
    collectd.register_config(vpn_status.configure_callback)
    #    collectd.register_init(vpn_status.BASE_TIME)
    collectd.register_read(vpn_status.read_callback)