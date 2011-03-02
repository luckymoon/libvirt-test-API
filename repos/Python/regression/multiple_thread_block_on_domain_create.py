#!/usr/bin/env python
"""testing https://bugzilla.redhat.com/show_bug.cgi?id=672226
"""

__author__ = "Guannan Ren <gren@redhat.com>"
__date__ = "Tue Mar 1, 2011"
__version__ = "0.1.0"
__credits__ = "Copyright (C) 2011 Red Hat, Inc."
__all__ = ['domain_list', 'get_option_list','check_default_option',
           'check_inactive_option', 'check_all_option']

import os
import sys
import re
import commands
import shutil
import urllib
import getpass
from threading import Thread

def append_path(path):
    """Append root path of package"""
    if path in sys.path:
        pass
    else:
        sys.path.append(path)

pwd = os.getcwd()
result = re.search('(.*)libvirt-test-API', pwd)
homepath = result.group(0)
append_path(homepath)

from lib.Python import connectAPI
from lib.Python import domainAPI
from utils.Python import utils
from utils.Python import env_parser
from utils.Python import xmlbuilder
from exception import LibvirtAPI

IMAG_PATH = "/var/lib/libvirt/images/"
DISK_DD = "dd if=/dev/zero of=%s bs=1 count=1 seek=6G"

def check_params(params):
    """Checking the arguments required"""

    logger = params['logger']
    mandatory_args = ['guestos','guestarch','guesttype','guestnum']

    for arg in mandatory_args:
        if arg not in params:
            logger.error("Argument %s is required." % arg)
            return 1

    return 0

def request_credentials(credentials, user_data):
    for credential in credentials:
        if credential[0] == connectAPI.VIR_CRED_AUTHNAME:
            # prompt the user to input a authname. display the provided message
            credential[4] = "root"

            # if the user just hits enter raw_input() returns an empty string.
            # in this case return the default result through the last item of
            # the list
            if len(credential[4]) == 0:
                credential[4] = credential[3]
        elif credential[0] == connectAPI.VIR_CRED_PASSPHRASE:
            # use the getpass module to prompt the user to input a password.
            # display the provided message and return the result through the
            # last item of the list
            credential[4] = "redhat"
        else:
            return -1

    return 0


class guest_install(Thread):
    """function callable by as a thread to create guest
    """
    def __init__(self, name, os, arch, type, ks, domobj, util, logger):
        Thread.__init__(self)
        self.name = name
        self.os = os
        self.arch = arch
        self.type = type
        self.ks = ks
        self.domobj = domobj
        self.util = util
        self.logger = logger

    def run(self):
        guest_params = {};
        guest_params['guesttype'] = self.type
        guest_params['guestname'] = self.name  
        guest_params['kickstart'] = self.ks
        macaddr = self.util.get_rand_mac()
        guest_params['macaddr'] = macaddr 
                     
	# prepare disk image file
        imagepath = IMAG_PATH + self.name
        (status, message) = commands.getstatusoutput(DISK_DD % imagepath)
        if status != 0:
            self.logger.debug(message)
        else:
            self.logger.info("creating disk images file is successful.")

        xmlobj = xmlbuilder.XmlBuilder() 
        guestxml = xmlobj.build_domain_install(guest_params)
        self.logger.debug("guestxml is %s" % guestxml)  
        self.logger.info('create guest %sfrom xml description' % self.name)
        try:
            guestobj = self.domobj.create(guestxml)
            self.logger.info('guest %s API createXML returned successfuly' % guestobj.name())
        except LibvirtAPI, e:
            self.logger.error("API error message: %s, error code is %s" %
                         (e.response()['message'], e.response()['code']))
            self.logger.error("fail to define domain %s" % guestname)
            return 1

        return 0
        
def multiple_thread_block_on_domain_create(params):
    """ spawn multiple threads to create guest simultaneously
        check the return status of calling create API
    """
    logger = params['logger']
    logger.info("start checking arguments")
    params_check_result = check_params(params)

    if params_check_result:
        return 1

    logger.info("Arguments checkup finished.")

    guestos = params.get('guestos')
    arch = params.get('guestarch')
    type = params.get('guesttype')
    num = params.get('guestnum')

    logger.info("the os of guest is %s" % guestos)
    logger.info("the arch of guest is %s" % arch)
    logger.info("the type of guest is %s" % type)
    logger.info("the number of guest we are going to install is %s" % num)

    util = utils.Utils()
    hypervisor = util.get_hypervisor()
    uri = util.get_uri('127.0.0.1')

    auth = [[connectAPI.VIR_CRED_AUTHNAME, connectAPI.VIR_CRED_PASSPHRASE], request_credentials, None]

    virconn = connectAPI.ConnectAPI().openAuth(uri, auth, 0)
    domobj = domainAPI.DomainAPI(virconn)

    logger.info("the type of hypervisor is %s" % hypervisor)
    logger.debug("the uri to connect is %s" % uri)

    envfile = os.path.join(homepath, 'env.cfg') 
    envpaser = env_parser.Envpaser(envfile)
    ostree = envpaser.get_value("guest", guestos + "_" + arch)
    ks = envpaser.get_value("guest", guestos + "_" + arch +
                                "_http_ks")

    # download vmlinuz and initrd.img
    vmlinuzpath = os.path.join(ostree, 'isolinux/vmlinuz')
    initrdpath = os.path.join(ostree, 'isolinux/initrd.img')

    urllib.urlretrieve(vmlinuzpath, '/var/lib/libvirt/boot/vmlinuz')
    urllib.urlretrieve(initrdpath, '/var/lib/libvirt/boot/initrd.img')


    name = "guest"
    thread_pid = []
    for i in range(0, int(num)): 
        guestname =  name + str(i)
        thr = guest_install(guestname, guestos, arch, type, ks, domobj, util, logger)
        thread_pid.append(thr)

    for id in thread_pid:
        id.start()
 
    for id in thread_pid:
        id.join()

    return 0













