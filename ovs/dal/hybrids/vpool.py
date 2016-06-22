# Copyright (C) 2016 iNuron NV
#
# This file is part of Open vStorage Open Source Edition (OSE),
# as available from
#
#      http://www.openvstorage.org and
#      http://www.openvstorage.com.
#
# This file is free software; you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License v3 (GNU AGPLv3)
# as published by the Free Software Foundation, in version 3 as it comes
# in the LICENSE.txt file of the Open vStorage OSE distribution.
#
# Open vStorage is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY of any kind.

"""
VPool module
"""
import time
from ovs.dal.dataobject import DataObject
from ovs.dal.hybrids.backendtype import BackendType
from ovs.dal.structures import Dynamic, Property, Relation
from ovs.extensions.storageserver.storagedriver import StorageDriverClient


class VPool(DataObject):
    """
    The VPool class represents a vPool. A vPool is a Virtual Storage Pool, a Filesystem, used to
    deploy vMachines. a vPool can span multiple Storage Drivers and connects to a single Storage BackendType.
    """
    STATUSES = DataObject.enumerator('Status', ['DELETING', 'EXTENDING', 'FAILURE', 'INSTALLING', 'RUNNING', 'SHRINKING'])

    __properties = [Property('name', str, doc='Name of the vPool'),
                    Property('description', str, mandatory=False, doc='Description of the vPool'),
                    Property('size', int, mandatory=False, doc='Size of the vPool expressed in Bytes. Set to zero if not applicable.'),
                    Property('login', str, mandatory=False, doc='Login/Username for the Storage BackendType.'),
                    Property('password', str, mandatory=False, doc='Password for the Storage BackendType.'),
                    Property('connection', str, mandatory=False, doc='Connection (IP, URL, Domain name, Zone, ...) for the Storage BackendType.'),
                    Property('metadata', dict, mandatory=False, doc='Metadata for the backends, as used by the Storage Drivers.'),
                    Property('rdma_enabled', bool, default=False, doc='Has the vpool been configured to use RDMA for DTL transport, which is only possible if all storagerouters are RDMA capable'),
                    Property('status', STATUSES.keys(), doc='Status of the vPool')]
    __relations = [Relation('backend_type', BackendType, 'vpools', doc='Type of storage backend.')]
    __dynamics = [Dynamic('configuration', dict, 3600),
                  Dynamic('statistics', dict, 4),
                  Dynamic('identifier', str, 120),
                  Dynamic('stored_data', int, 60)]
    _fixed_properties = ['storagedriver_client']

    def __init__(self, *args, **kwargs):
        """
        Initializes a vPool, setting up its additional helpers
        """
        DataObject.__init__(self, *args, **kwargs)
        self._frozen = False
        self._storagedriver_client = None
        self._frozen = True

    @property
    def storagedriver_client(self):
        """
        Client used for communication between Storage Driver and framework
        :return: StorageDriverClient
        """
        if self._storagedriver_client is None:
            self.reload_client()
        return self._storagedriver_client

    def _configuration(self):
        """
        VPool configuration
        """
        from ovs.lib.vpool import VPoolController
        return VPoolController.get_configuration(self.guid)

    def _statistics(self, dynamic):
        """
        Aggregates the Statistics (IOPS, Bandwidth, ...) of each vDisk served by the vPool.
        """
        from ovs.dal.hybrids.vdisk import VDisk
        statistics = {}
        for key in StorageDriverClient.STAT_KEYS:
            statistics[key] = 0
            statistics['{0}_ps'.format(key)] = 0
        for storagedriver in self.storagedrivers:
            for key, value in storagedriver.fetch_statistics().iteritems():
                statistics[key] += value
        statistics['timestamp'] = time.time()
        VDisk.calculate_delta(self._key, dynamic, statistics)
        return statistics

    def _stored_data(self):
        """
        Aggregates the Stored Data of each vDisk served by the vPool.
        """
        return self.statistics['stored']

    def _identifier(self):
        """
        An identifier of this vPool in its current configuration state
        """
        return '{0}_{1}'.format(self.guid, '_'.join(self.storagedrivers_guids))

    def reload_client(self):
        """
        Reloads the StorageDriver Client
        """
        self._frozen = False
        self._storagedriver_client = StorageDriverClient.load(self)
        self._frozen = True
