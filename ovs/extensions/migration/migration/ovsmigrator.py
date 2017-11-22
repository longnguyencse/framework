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
OVS migration module
"""

from ovs.extensions.generic.logger import Logger


class OVSMigrator(object):
    """
    Handles all model related migrations
    """

    identifier = 'ovs'  # Used by migrator.py, so don't remove
    THIS_VERSION = 14

    _logger = Logger('extensions')

    def __init__(self):
        """ Init method """
        pass

    @staticmethod
    def migrate(previous_version, master_ips=None, extra_ips=None):
        """
        Migrates from a given version to the current version. It uses 'previous_version' to be smart
        wherever possible, but the code should be able to migrate any version towards the expected version.
        When this is not possible, the code can set a minimum version and raise when it is not met.
        :param previous_version: The previous version from which to start the migration
        :type previous_version: float
        :param master_ips: IP addresses of the MASTER nodes
        :type master_ips: list or None
        :param extra_ips: IP addresses of the EXTRA nodes
        :type extra_ips: list or None
        """

        _ = master_ips, extra_ips
        working_version = previous_version

        # From here on, all actual migration should happen to get to the expected state for THIS RELEASE
        if working_version < OVSMigrator.THIS_VERSION:
            try:
                from ovs.dal.lists.storagerouterlist import StorageRouterList
                from ovs.dal.lists.vpoollist import VPoolList
                from ovs.extensions.generic.configuration import Configuration
                from ovs.extensions.packages.packagefactory import PackageFactory
                from ovs.extensions.services.servicefactory import ServiceFactory
                from ovs.extensions.generic.sshclient import SSHClient
                from ovs.extensions.generic.system import System
                local_machine_id = System.get_my_machine_id()
                local_ip = Configuration.get('/ovs/framework/hosts/{0}/ip'.format(local_machine_id))
                local_client = SSHClient(endpoint=local_ip, username='root')

                # Multiple Proxies
                if local_client.dir_exists(directory='/opt/OpenvStorage/config/storagedriver/storagedriver'):
                    local_client.dir_delete(directories=['/opt/OpenvStorage/config/storagedriver/storagedriver'])

                # MDS safety granularity on vPool level
                mds_safety_key = '/ovs/framework/storagedriver'
                if Configuration.exists(key=mds_safety_key):
                    current_mds_settings = Configuration.get(key=mds_safety_key)
                    for vpool in VPoolList.get_vpools():
                        vpool_key = '/ovs/vpools/{0}'.format(vpool.guid)
                        if Configuration.dir_exists(key=vpool_key):
                            Configuration.set(key='{0}/mds_config'.format(vpool_key),
                                              value=current_mds_settings)
                    Configuration.delete(key=mds_safety_key)

                # Introduction of edition key
                if Configuration.get(key=Configuration.EDITION_KEY, default=None) not in [PackageFactory.EDITION_COMMUNITY, PackageFactory.EDITION_ENTERPRISE]:
                    for storagerouter in StorageRouterList.get_storagerouters():
                        try:
                            Configuration.set(key=Configuration.EDITION_KEY, value=storagerouter.features['alba']['edition'])
                            break
                        except:
                            continue

                # Storing actual package name in version files
                voldrv_pkg_name, _ = PackageFactory.get_package_and_version_cmd_for(component=PackageFactory.COMP_SD)
                for file_name in local_client.file_list(directory=ServiceFactory.RUN_FILE_DIR):
                    if not file_name.endswith('.version'):
                        continue
                    file_path = '{0}/{1}'.format(ServiceFactory.RUN_FILE_DIR, file_name)
                    contents = local_client.file_read(filename=file_path)
                    if voldrv_pkg_name == PackageFactory.PKG_VOLDRV_SERVER:
                        if 'volumedriver-server' in contents:
                            contents = contents.replace('volumedriver-server', PackageFactory.PKG_VOLDRV_SERVER)
                            local_client.file_write(filename=file_path, contents=contents)
                    elif voldrv_pkg_name == PackageFactory.PKG_VOLDRV_SERVER_EE:
                        if 'volumedriver-server' in contents or PackageFactory.PKG_VOLDRV_SERVER in contents:
                            contents = contents.replace('volumedriver-server', PackageFactory.PKG_VOLDRV_SERVER_EE)
                            contents = contents.replace(PackageFactory.PKG_VOLDRV_SERVER, PackageFactory.PKG_VOLDRV_SERVER_EE)
                            local_client.file_write(filename=file_path, contents=contents)
            except:
                OVSMigrator._logger.exception('Error occurred while executing the migration code')
                # Don't update migration version with latest version, resulting in next migration trying again to execute this code
                return OVSMigrator.THIS_VERSION - 1

        return OVSMigrator.THIS_VERSION
