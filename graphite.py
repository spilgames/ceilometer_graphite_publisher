# -*- encoding: utf-8 -*-
#
# Copyright 2014 Sashi Dahal, Robert van Leeuwen
#
# Author: Sashi Dahal <shashi.dahal@spilgames.com>
# Author: Robert van Leeuwen <robert.vanleeuwen@spilgames.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Publish to Graphite
"""

from ceilometer import publisher
from ceilometer.openstack.common import log
from ceilometer.openstack.common import network_utils
from ceilometer.openstack.common.gettextutils import _
import socket
from oslo.config import cfg

import time
import re

cfg.CONF.import_opt('udp_port', 'ceilometer.collector',
                    group='collector')


OPTS = [
    cfg.StrOpt('prefix',
               default='ceilometer',
               help='Graphite prefix key'),
    cfg.BoolOpt('hypervisor_in_prefix',
               default=True,
               help='If the hypervisor should be added to the prefix'),
]

cfg.CONF.register_opts(OPTS, group="graphite")


#cfg.CONF.import_opt('prefix', 'append_hostname', group='graphite')

LOG = log.getLogger(__name__)

class GraphitePublisher(publisher.PublisherBase):

    def __init__(self, parsed_url):
        self.host, self.port = network_utils.parse_host_port(
            parsed_url.netloc,
            default_port=cfg.CONF.collector.udp_port)

        if cfg.CONF.graphite.hypervisor_in_prefix:
            self.prefix = cfg.CONF.graphite.prefix + socket.gethostname().split('.')[0] + "."
        else :
            self.prefix = cfg.CONF.graphite.prefix


    def graphitePush(self, metric):
        LOG.debug("Sending graphite metric:" + metric)
        graphiteSock = socket.socket() # TCP
        #graphiteSock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM) # UDP
        graphiteSock.connect((self.host, self.port))
        graphiteSock.sendall(metric)
        graphiteSock.close()


    def publish_samples(self, context, samples):

        for sample in samples:

            stats_time = time.time()

            msg = sample.as_dict()
            prefix = self.prefix


            ## for getting a clear idea of the attributes ##
            resource_id = msg['resource_id']
            project_id = msg['project_id']
            data_type = msg['type'] # gauge, cumulative, delta
            volume = msg['volume'] # usage
            metric_name = msg['name'] # network,instance,cpu, disk etc ..
            metadata = msg['resource_metadata']

            instance_match = re.match('instance', metric_name)
            network_match = re.match('network', metric_name)
            disk_match = re.match('disk', metric_name)

            ## ram,cpu, and disk is not present on all metrics ##
            if disk_match:
                ram = metadata['memory_mb']
                vcpus = metadata['vcpus']
                disk_gb = metadata['disk_gb']
                vmid = metadata.get('instance_id')

            if network_match:
                vmid = metadata.get('instance_id')
                vm = vmid

            else:
                vm = resource_id

            if disk_match:
                vmram = "%s%s.%s.memory %s %d\n" %(prefix, project_id, vm, ram , stats_time)
                vmcpu = "%s%s.%s.cpu_count %s %d\n" %(prefix, project_id, vm, vcpus , stats_time)
                vmdisk = "%s%s.%s.disk_space %s %d\n" %(prefix, project_id, vm, disk_gb , stats_time)

                LOG.debug(_("[+] Graphite %s" %vmram))
                LOG.debug(_("[+] Graphite %s" %vmcpu))
                LOG.debug(_("[+] Graphite %s" %vmdisk))


            ## build the metrics to send to graphite ##
            ## We are only interested in the gauge data
            ## Skipping Instance related metrics ##

            if data_type == 'gauge' and instance_match is None:

                stats_time = time.time()

                vmstat = "%s%s.%s.%s %s %d\n" %(prefix, project_id, vm, metric_name, volume, stats_time)
                self.graphitePush(vmstat)

                if disk_match:
                    self.graphitePush(vmram)
                    self.graphitePush(vmcpu)
                    self.graphitePush(vmdisk)

                print ""

            else:
                LOG.debug(_("[-]"))


            try:
                LOG.debug(_("OK"))

            except Exception as e:
                LOG.warn(_("Unable to send to Graphite"))
                LOG.exception(e)

