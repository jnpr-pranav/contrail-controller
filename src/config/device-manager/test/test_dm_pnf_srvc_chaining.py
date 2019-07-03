#
# Copyright (c) 2019 Juniper Networks, Inc. All rights reserved.
#
import gevent
import json
from attrdict import AttrDict
from device_manager.device_manager import DeviceManager
from cfgm_common.tests.test_common import retries
from cfgm_common.tests.test_common import retry_exc_handler
from test_dm_ansible_common import TestAnsibleCommonDM
from test_dm_utils import FakeJobHandler
from vnc_api.vnc_api import *


class TestAnsiblePNFSrvcChainingDM(TestAnsibleCommonDM):

    def test_pnf_required_params(self):
        (jt, fabric, node_profiles, role_configs,
         physical_routers, bgp_routers) = self.create_base_objects()

        abstract_config = self.check_dm_ansible_config_push()
        print(json.dumps(abstract_config, indent=4, sort_keys=True))

        self.destroy_base_objects(
            jt, fabric, node_profiles, role_configs,
            physical_routers, bgp_routers)

    # end test_pnf_required_params

    def create_base_objects(self):
        jt = self.create_job_template('job-template-1')
        fabric = self.create_fabric('fabric-1')

        np_srx, rc_srx = self.create_node_profile(
            'node-profile-1', device_family='junos',
            role_mappings=[
                AttrDict({
                    'physical_role': 'pnf',
                    'rb_roles': ['PNF-Servicechain']
                })
            ],
            job_template=jt)

        np_qfx, rc_qfx = self.create_node_profile(
            'node-profile-2', device_family='junos-qfx',
            role_mappings=[
                AttrDict({
                    'physical_role': 'spine',
                    'rb_roles': ['CRB-MCAST-Gateway', 'PNF-Servicechain']
                })
            ],
            job_template=jt
        )

        bgp_srx, pr_srx = self.create_router(
            'srx_router' + self.id(), '2.2.2.2',
            product='srx5400', family='junos',
            role='pnf', rb_roles=['PNF-Servicechain'],
            fabric=fabric, node_profile=np_srx
        )

        bgp_qfx, pr_qfx = self.create_router(
            'qfx_router' + self.id(), '4.4.4.4',
            product='qfx5110', family='junos-qfx',
            role='spine', rb_roles=['CRB-MCAST-Gateway', 'PNF-Servicechain'],
            fabric=fabric, node_profile=np_qfx
        )

        node_profiles = [np_srx, np_qfx]
        role_configs = [rc_srx, rc_qfx]
        physical_routers = [pr_srx, pr_qfx]
        bgp_routers = [bgp_srx, bgp_qfx]

        return (jt, fabric, node_profiles, role_configs,
                physical_routers, bgp_routers)

    # end create_required_objects

    def destroy_base_objects(
            self, job_template, fabric, node_profiles, role_configs,
            physical_routers, bgp_routers
            ):
        # Delete Physical Routers
        for pr in physical_routers:
            self.delete_routers(None, pr)
            self.wait_for_routers_delete(None, pr.get_fq_name())

        # Delete BGP Routers
        for bgpr in bgp_routers:
            self._vnc_lib.bgp_router_delete(fq_name=bgpr.get_fq_name())

        # Delete Role Configs
        for rc in role_configs:
            self._vnc_lib.role_config_delete(fq_name=rc.get_fq_name())

        # Delete Node Profiles:
        for np in node_profiles:
            self._vnc_lib.node_profile_delete(fq_name=np.get_fq_name())

        # Delete Fabric
        self._vnc_lib.fabric_delete(fq_name=fabric.get_fq_name())

        # Delete Job Temppalte
        self._vnc_lib.job_template_delete(fq_name=job_template.get_fq_name())

    # end destroy_created_objects

    # TODO Create Logical Interfaces
    # TODO Create Service Appliance Set
    # TODO Create Service Template
    # TODO Create Service Instance
    # TODO Create Service Appliance
    # TODO Create Port Tuple

# end TestAnsiblePNFSrvcChainingDM
