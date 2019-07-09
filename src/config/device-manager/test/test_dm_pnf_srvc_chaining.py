#
# Copyright (c) 2019 Juniper Networks, Inc. All rights reserved.
#
import gevent
import json
import sys
from attrdict import AttrDict
from device_manager.device_manager import DeviceManager
from cfgm_common.tests.test_common import retries
from cfgm_common.tests.test_common import retry_exc_handler
from test_dm_ansible_common import TestAnsibleCommonDM
from test_dm_utils import FakeJobHandler
from vnc_api.vnc_api import *


class TestAnsiblePNFSrvcChainingDM(TestAnsibleCommonDM):

    def test_pnf_required_params(self):
        # Create base objects
        (jt, fabric, node_profiles, role_configs,
         physical_routers, bgp_routers) = self.create_base_objects()

        # Get Individual Physical Routers
        srx = physical_routers[0]
        qfx = physical_routers[1]

        # Create VMI and PIs for srx
        vxlan_id_srx = 5
        vn_obj_srx = self.create_vn(str(vxlan_id_srx), '5.5.5.0')
        port_vlan_tag_srx = 50
        vlan_tag_srx = 0
        vmi_srx, vm_srx, pi_list_srx = self.attach_vmi(
            str(vxlan_id_srx), ['xe-1/0/0', 'xe-1/0/1'], [srx, srx],
            vn_obj_srx, None, fabric, None, port_vlan_tag_srx)

        # Create VMI and PIs for qfx
        vxlan_id_qfx = 7
        vn_obj_qfx = self.create_vn(str(vxlan_id_qfx), '7.7.7.0')
        port_vlan_tag_qfx = 70
        vlan_tag_qfx = 0
        vmi_qfx, vm_qfx, pi_list_qfx = self.attach_vmi(
            str(vxlan_id_qfx), ['xe-1/1/0', 'xe-1/1/1'], [qfx, qfx],
            vn_obj_qfx, None, fabric, None, port_vlan_tag_qfx)

        # Create Left Logical Router
        llr = LogicalRouter("left_lr")
        llr.set_physical_router(qfx)
        llr_uuid = self._vnc_lib.logical_router_create(llr)
        llr = self._vnc_lib.logical_router_read(id=llr_uuid)

        # Create Right Logical Router
        rlr = LogicalRouter("right_lr")
        rlr.set_physical_router(qfx)
        rlr_uuid = self._vnc_lib.logical_router_create(rlr)
        rlr = self._vnc_lib.logical_router_read(id=rlr_uuid)

        # Create Service Objects
        (sas_obj, st_obj, sa_obj,
         si_obj, pt_obj) = self.create_service_objects()

        print("========================================")
        print("===========STARTED DESTROYING===========")
        print("========================================")

        # Destroy service objects
        self.delete_service_objects(sas_obj, st_obj, sa_obj, si_obj, pt_obj)

        # Destroy Logical Routers
        for lr in [llr, rlr]:
            self._vnc_lib.logical_router_delete(fq_name=lr.get_fq_name())

        # Destroy vmis, vms, physical interfaces and vns
        for vmi in [vmi_srx, vmi_qfx]:
            self._vnc_lib.virtual_machine_interface_delete(
                fq_name=vmi.get_fq_name())

        for vm in [vm_srx, vm_qfx]:
            self._vnc_lib.virtual_machine_delete(fq_name=vm.get_fq_name())

        for pi_list in [pi_list_srx, pi_list_qfx]:
            for idx in range(len(pi_list)):
                self._vnc_lib.physical_interface_delete(
                    fq_name=pi_list[idx].get_fq_name())

        for vn_obj in [vn_obj_srx, vn_obj_qfx]:
            self._vnc_lib.virtual_network_delete(fq_name=vn_obj.get_fq_name())

        # Destroy Base Objects
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

        gevent.sleep(1)

        return (jt, fabric, node_profiles, role_configs,
                physical_routers, bgp_routers)
    # end create_required_objects

    def destroy_base_objects(
            self, job_template, fabric, node_profiles, role_configs,
            physical_routers, bgp_routers
            ):
        # Delete BGP Routers, Physical Routers
        for bgpr, pr in zip(bgp_routers, physical_routers):
            self.delete_routers(bgpr, pr)
            self.wait_for_routers_delete(bgpr.get_fq_name(), pr.get_fq_name())

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

    # TODO Create VMI

    # TODO Create Service Appliance Set
    def create_service_appliance_set(self, name):
        sas_obj = ServiceApplianceSet(
            name=name, parent_type='global-system-config',
            fq_name=[self.GSC, name])

        sas_obj.set_service_appliance_set_virtualization_type(
            "physical-device")
        # TODO SAS Properties

        sas_uuid = self._vnc_lib.service_appliance_set_create(sas_obj)
        sas_obj = self._vnc_lib.service_appliance_set_read(id=sas_uuid)

        return sas_obj
    # end create_service_appliance_set

    # TODO Create Service Template
    def create_service_template(self, name, sas_obj):

        st_obj = ServiceTemplate(name=name)

        st_uuid = self._vnc_lib.service_template_create(st_obj)
        st_obj.set_service_appliance_set(sas_obj)

        try:
            svc_properties = ServiceTemplateType()
            svc_properties.set_service_virtualization_type(
                "physical-device")
            if_type = ServiceTemplateInterfaceType()
            if_type.set_service_interface_type('left')
            svc_properties.add_interface_type(if_type)
            if_type = ServiceTemplateInterfaceType()
            if_type.set_service_interface_type('right')
            svc_properties.add_interface_type(if_type)
        except AttributeError:
            print("Warning: Service template could not be fully updated ")
        else:
            st_obj.set_service_template_properties(svc_properties)
            self._vnc_lib.service_template_update(st_obj)
            st_obj = self._vnc_lib.service_template_read(id=st_uuid)
            return st_obj
    # end create_service_template

    # TODO Create Service Appliance
    def create_service_appliance(self, name, sas_obj):
        default_gsc_name = "default-global-system-config"
        sas_fq_name = sas_obj.get_fq_name()
        right_attachment_point = ("qfx_routertest.test_dm_pnf_srvc_chaining."
                                  "TestAnsiblePNFSrvcChainingDM."
                                  "test_pnf_required_params:xe-1/1/0")
        left_attachment_point = ("qfx_routertest.test_dm_pnf_srvc_chaining."
                                 "TestAnsiblePNFSrvcChainingDM."
                                 "test_pnf_required_params:xe-1/1/1")
        pnf_left_intf = ("srx_routertest.test_dm_pnf_srvc_chaining."
                         "TestAnsiblePNFSrvcChainingDM."
                         "test_pnf_required_params:xe-1/0/0")
        pnf_right_intf = ("srx_routertest.test_dm_pnf_srvc_chaining."
                          "TestAnsiblePNFSrvcChainingDM."
                          "test_pnf_required_params:xe-1/0/1")
        try:
            sas_obj = self._vnc_lib.service_appliance_set_read(
                                                       fq_name=sas_fq_name)
        except NoIdError:
            print("Error: Service Appliance Set does not exist")
            sys.exit(-1)

        sa_obj = ServiceAppliance(name, sas_obj)

        try:
            kvp_array = []
            kvp = KeyValuePair(
                "left-attachment-point",
                default_gsc_name + ':' + left_attachment_point)
            kvp_array.append(kvp)
            kvp = KeyValuePair(
                "right-attachment-point",
                default_gsc_name + ':' + right_attachment_point)
            kvp_array.append(kvp)
            kvps = KeyValuePairs()
            kvps.set_key_value_pair(kvp_array)
            sa_obj.set_service_appliance_properties(kvps)
            sa_obj.set_service_appliance_virtualization_type("physical-device")
        except AttributeError:
            print("Warning: Some attributes of Service Appliance missing ")

        try:
            pnf_left_intf_obj = self._vnc_lib.physical_interface_read(
                fq_name=[
                    default_gsc_name, pnf_left_intf.split(":")[0],
                    pnf_left_intf.split(":")[-1]])
            attr = ServiceApplianceInterfaceType(interface_type='left')
            sa_obj.add_physical_interface(pnf_left_intf_obj, attr)
        except NoIdError:
            print("Error: Left PNF interface does not exist")
            sys.exit(-1)
        except AttributeError:
            print("Error: Left PNF interface missing")
            sys.exit(-1)

        try:
            pnf_right_intf_obj = self._vnc_lib.physical_interface_read(
                    fq_name=[
                        default_gsc_name, pnf_right_intf.split(":")[0],
                        pnf_right_intf.split(":")[-1]])
            attr = ServiceApplianceInterfaceType(interface_type='right')
            sa_obj.add_physical_interface(pnf_right_intf_obj, attr)
        except NoIdError:
            print("Error: Right PNF interface does not exist")
            sys.exit(-1)
        except AttributeError:
            print("Error: Right PNF interface missing")
            sys.exit(-1)

        sa_uuid = self._vnc_lib.service_appliance_create(sa_obj)
        sa_obj = self._vnc_lib.service_appliance_read(id=sa_uuid)

        return sa_obj
    # end create_service_appliance

    # TODO Create Service Instance
    def create_service_instance(self, name, st_obj):
        si_obj = ServiceInstance(name=name)

        si_obj.add_service_template(st_obj)

        left_svc_vlan = '1000'
        right_svc_vlan = '1001'
        left_svc_asns = '66000, 66001'
        right_svc_asns = '66000, 66002'

        try:
            kvp_array = []
            kvp = KeyValuePair("left-svc-vlan", left_svc_vlan)
            kvp_array.append(kvp)
            kvp = KeyValuePair("right-svc-vlan", right_svc_vlan)
            kvp_array.append(kvp)
            kvp = KeyValuePair("left-svc-asns", left_svc_asns)
            kvp_array.append(kvp)
            kvp = KeyValuePair("right-svc-asns", right_svc_asns)
            kvp_array.append(kvp)
            kvps = KeyValuePairs()
            kvps.set_key_value_pair(kvp_array)
            si_obj.set_annotations(kvps)
            props = ServiceInstanceType()
            props.set_service_virtualization_type("physical-device")
            props.set_ha_mode("active-standby")
            si_obj.set_service_instance_properties(props)
        except AttributeError:
            print("Warning: Some attributes of Service Instance missing")

        si_uuid = self._vnc_lib.service_instance_create(si_obj)
        si_obj = self._vnc_lib.service_instance_read(id=si_uuid)

        return si_obj
    # end create_service_instance

    # TODO Create Port Tuple
    def create_port_tuple(self, name, si_obj):
        si_fq_name = si_obj.get_fq_name()
        left_lr_name = "left_lr"
        right_lr_name = "right_lr"

        try:
            si_obj = self._vnc_lib.service_instance_read(fq_name=si_fq_name)
        except NoIdError:
            print "Service Instance Not found " + (si_name)
            sys.exit(-1)

        pt_obj = PortTuple(name, parent_obj=si_obj)

        try:
            left_lr_fq_name = ['default-domain',
                               'default-project',
                               left_lr_name]
            right_lr_fq_name = ['default-domain',
                                'default-project',
                                right_lr_name]
            left_lr_obj = self._vnc_lib.logical_router_read(
                                                     fq_name=left_lr_fq_name)
            right_lr_obj = self._vnc_lib.logical_router_read(
                                                    fq_name=right_lr_fq_name)
            pt_obj.add_logical_router(left_lr_obj)
            pt_obj.add_logical_router(right_lr_obj)
        except NoIdError as e:
            print("Error! LR not found " + (e.message))
            sys.exit(-1)

        try:
            kvp_array = []
            kvp = KeyValuePair("left-lr", left_lr_obj.uuid)
            kvp_array.append(kvp)
            kvp = KeyValuePair("right-lr", right_lr_obj.uuid)
            kvp_array.append(kvp)
            kvps = KeyValuePairs()
            kvps.set_key_value_pair(kvp_array)
            pt_obj.set_annotations(kvps)
        except AttributeError:
            print("Warning: Some attributes of PT missing " + pt_name)

        pt_uuid = self._vnc_lib.port_tuple_create(pt_obj)
        pt_obj = self._vnc_lib.port_tuple_read(id=pt_uuid)

        return pt_obj
    # end create_port_tuple

    def create_service_objects(self):
        sas_obj = self.create_service_appliance_set(name="sas")
        st_obj = self.create_service_template(name="st", sas_obj=sas_obj)
        sa_obj = self.create_service_appliance(name="sa", sas_obj=sas_obj)
        si_obj = self.create_service_instance(name="si", st_obj=st_obj)
        pt_obj = self.create_port_tuple(name="pt", si_obj=si_obj)

        return (sas_obj, st_obj, sa_obj, si_obj, pt_obj)
    # end create_service_objects

    def delete_service_objects(self, sas, st, sa, si, pt):
        # Delete Port Tuple
        self._vnc_lib.port_tuple_delete(fq_name=pt.get_fq_name())
        # Delete Service Instance
        self._vnc_lib.service_instance_delete(fq_name=si.get_fq_name())
        # Delete Service Appliance
        self._vnc_lib.service_appliance_delete(fq_name=sa.get_fq_name())
        # Delete Service Template
        self._vnc_lib.service_template_delete(fq_name=st.get_fq_name())
        # Delete Service Appliance Set
        self._vnc_lib.service_appliance_set_delete(fq_name=sas.get_fq_name())
    # end delete_service_objects

    def print_all_objects(self):
        # Print all job templates
        print(json.dumps(self._vnc_lib.job_templates_list(), indent=4))
        # Print all fabrics
        print(json.dumps(self._vnc_lib.fabrics_list(), indent=4))
        # Print all node profiles
        print(json.dumps(self._vnc_lib.node_profiles_list(), indent=4))
        # Print all physical routers
        print(json.dumps(self._vnc_lib.physical_routers_list(), indent=4))
        # Print all bgp routers
        print(json.dumps(self._vnc_lib.bgp_routers_list(), indent=4))
        # Print all logical routers
        print(json.dumps(self._vnc_lib.logical_routers_list(), indent=4))
        # Print all physical interfaces
        print(json.dumps(self._vnc_lib.physical_interfaces_list(), indent=4))
        # Print all sas objects
        print(json.dumps(
            self._vnc_lib.service_appliance_sets_list(), indent=4))
        # Print all service template objects
        print(json.dumps(self._vnc_lib.service_templates_list(), indent=4))
        # Print all service appliance objects
        print(json.dumps(self._vnc_lib.service_appliances_list(), indent=4))
        # Print all service instance objects
        print(json.dumps(self._vnc_lib.service_instances_list(), indent=4))
        # Print all port tuples
        print(json.dumps(self._vnc_lib.port_tuples_list(), indent=4))
    # end print_all_objects
# end TestAnsiblePNFSrvcChainingDM
