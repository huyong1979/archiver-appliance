# -*- coding: utf-8 -*-
'''The purpose of this module is to provide a higher level of functions, utilizing 
the class methods implemented in epicsarchiver.py, to more easily manage AA.'''

from __future__ import print_function
import os
import sys
import time
import re
import glob
from collections import OrderedDict as odict
from epicsarchiver import ArchiverAppliance

# get the Archiver's FULL hostname: localhost or hostname defined in aa.conf 
import socket
localhost = socket.getfqdn()

import ConfigParser
config = ConfigParser.ConfigParser()
config.optionxform = str #keep keys as its original
# user home directory settings will overwrite system config(/etc/...), 
# system config will overwrite aa.conf in the current working directory
aa_conf_user = os.path.expanduser('~/aa.conf')
config.read(['aa.conf', '/etc/default/aa.conf', aa_conf_user])
aaconfig_dict = {}
sections = config.sections()
for section in sections:
    aaconfig_dict[section] = dict(config.items(section))
if not aaconfig_dict:
    print("Aborted: no aa.conf found or something wrong inside aa.conf")
    sys.exit("Please exit python/ipython shell if the shell does not exit \
by itself, make changes on aa.conf, then try again.")

try:
    archiver = ArchiverAppliance(str(localhost))
    print("{}: {}".format(localhost, archiver.version))
except:
    try:
        archiver = ArchiverAppliance(hostname=str(aaconfig_dict['Host']['Name']))
        print(archiver.version)
    except:
        print("Aborted: the Archiver server is not {} and it is not correctly \
set in aa.conf (or /etc/default/aa.conf or {}.)\n".format(localhost, aa_conf_user))
        sys.exit("Please exit python/ipython shell if the shell does not exit \
by itself. Make changes on aa.conf, then try again.")


import subprocess
log_dir = os.path.expanduser("~") + "/aa-script-logs"
subprocess.call(['mkdir', '-p', log_dir])

def _log(results, file_prefix, one_line_per_pvinfo=True, **kargs):
    '''Save results, which may include pv names as well as other information, 
    to a text file. one_line_per_pvinfo makes .txt file more easier to be 
    analyzied by other software such as Microsoft Excel 
    '''
    if not results:
        print("Nothing to be logged for %s"%file_prefix)
        return
            
    timestamp = str(time.strftime("-%Y%b%d_%H%M%S"))
    prefix = str(file_prefix).replace(" ", "-")
    file_name = log_dir + "/" + prefix +'-'+str(len(results)) + timestamp+".txt"

    with open(str(file_name), 'w') as fd:
        if isinstance(results[0], unicode) or isinstance(results[0], str):
            for result in results:
                fd.write(str(result) + "\n")
        elif isinstance(results[0], odict) or isinstance(results[0], dict):
            for pv_dict in results:
                for (k, v) in pv_dict.iteritems():
                    fd.write(str(k+"\t")+str(v)+"\t")
                    if not one_line_per_pvinfo:
                        fd.write("\n")
                        
                fd.write("\n")

    print("{} PV items have been written to {}.".format(len(results), file_name))
    print("Use MS Excel or OpenOffice Spreadsheet(Insert Sheet from File ...) \
to open the txt file for better viewing. \n")


def _get_pvnames(results, sort=True, do_return=True, **kargs):
    '''Get PV names from results which might be a list of dicts, then sorted them.
    To avoid verbose output when using python/ipython shell, set do_return=False'''
    if not results:
        print("No PVs found\n")
        return

    pvnames=results
    if isinstance(results[0], dict): 
        pvnames = [dic['pvName'] for dic in results]
        
    if sort:
        pvnames.sort()

    if len(pvnames) > 10:
        pvs_4print=pvnames[:9]
    else:
        pvs_4print=pvnames
    for pv in pvs_4print:
        print(pv)
    print("...\n%d PVs\n"%len(pvnames))
    
    if do_return:
        return pvnames


def get_pvnames_from_file(filename='pvlist.txt'):
    '''pvnames in 'filename' should be listed as one column'''
    with open(filename, "r") as fd:
        lines = fd.readlines()
        pvname_list = []
        for line in lines:
            line = str(line).strip() # do the stip() first
            # Remove empty lines and lines that start with "#"            
            if line.startswith("#") or line == "":
                continue
            pvname_list.append(line)
            
    pvnames = list(set(pvname_list)) # remove duplicated PVs
    pvnames.sort()
    print("get %d PVs from %s"%(len(pvnames), filename))
    return pvnames


def get_pvs_file_info(pvnames,only_report_total_size=True,report_current_year=True,
                      lts_path=str(aaconfig_dict["Lts"]["Path"]), **kargs):
    '''- Get archived data file name and file size for each pvname in pvnames.
    pvname = "SR-RF{CFD:2-Cav}E:I"; relative_path = 'SR/RF/CFD/2/Cav/E/I';
    pb_file: lts_path/SR/RF/CFD/2/Cav/E/I:2016.pb. '''
    if not os.path.isdir(lts_path):
        print("Aborted: the long-term storage(lts) path '{}' seems not correct,\
please reconfigure it in aa.conf".format(lts_path))
        sys.exit("Please exit python/ipython shell if the shell does not exit \
by itself. Make changes on aa.conf, then try again.")

    pvs_file_info = []
    zero_size_pvnames = []
    for pvname in pvnames:
        pv_file_info = odict()
        total_GB = 0.0
        file_names = ""
        # replace the special characters, ':', '{', '}', '-', with '/'
        relative_path = re.sub('[:{}-]', '/', pvname) #this is specific for NSLS-2
        #relative_path = re.sub('[char_set]', '/', pvname)
        full_path = lts_path + '/' + str(relative_path)
        
        for pb_file in glob.glob(full_path+'*'):
            year = "".join("".join(pb_file.rsplit(full_path+':'))).rsplit('.pb')[0]
            size_GB = round(1.0*os.path.getsize(pb_file)/(1024**3), 9)
            total_GB += size_GB
            if not only_report_total_size:
                pv_file_info[pvname+'('+year+')'] = size_GB # GB per year
            if report_current_year:
                if year == time.strftime("%Y"):
                    file_names = pb_file
                    pv_file_info[pvname+" "+year] = size_GB
            else:
                file_names += (pb_file + "    ")

        if not total_GB: # zero-size
            zero_size_pvnames.append(pvname)
                
        pv_file_info[pvname+'(total)'] = total_GB # total file size (GB) for  pv 
        pv_file_info[pvname+'(path)'] = full_path
        pv_file_info[pvname+'(file_names)'] = file_names

        pvs_file_info.append(pv_file_info)

    return (pvs_file_info, zero_size_pvnames)
            

def report(report_type="", **kargs):
    '''A generic function which does more then just 'reporting something': it 
    gets data from the Archiver, parses those data to get pv names, does all 
    kinds of logs, and finally returns pv names if needed. 
    Supported keyword arguments:
      1) do_return=True: return pv names only; can be used for all report_*(); 
      2) log_file_info=True: write pvs' file info (name, size, etc.) to a file;
      3) filename='your-customized-text-file': used for report_pvs_from_file();
      4) pattern=something-like-'SR:C03-BI*': used for report_pvs();  
      5) regex='*': used for report_pvs();  
      6) limit=max-number-of-pvs: for get_storage_rate_report() and report_pvs(); 
      7) one_line_per_pvinfo: if False, key & value per line in the log file;
      8) sort: if False, pv names are not sorted;
      And the following can be used if log_file_info=True: lts_path,
      only_report_total_size, report_current_year. '''
    print("keyword arguments: {}".format(kargs))
    if report_type == 'never connected':
        results =  archiver.get_never_connected_pvs()
    elif report_type == 'currently disconnected':
        results = archiver.get_currently_disconnected_pvs()
    elif report_type == 'paused':
        results = archiver.get_paused_pvs_report()
    elif report_type == 'storage rate':
        results = archiver.get_storage_rate_report(limit=kargs.pop('limit',1000))
    elif report_type == 'waveform':
        results = archiver.get_archived_waveforms()
    elif report_type == 'search':
        results = archiver.get_all_pvs(pv=kargs.pop('pattern', '*'), 
            regex=kargs.pop('regex', '*'), limit=kargs.pop('limit', 1000))
    elif report_type == 'pvs from file':
        results = get_pvnames_from_file(kargs.pop('filename', 'pvlist.txt'))
                 
    pvnames = _get_pvnames(results, **kargs)    
    _log(pvnames, report_type + " pvnames", **kargs)
    
    if len(results) > 0:
        if isinstance(results[0], dict):
            _log(results, report_type + " details", **kargs)
    
    if kargs.pop('log_file_info', False):
        info = get_pvs_file_info(pvnames, **kargs)
        _log(info[0], report_type + " pvs file info", **kargs)   
        if len(info[1]) > 0: 
            zero_size_pvnames = info[1]
            zero_size_pvnames.sort()
            _log(zero_size_pvnames, report_type + " zero-size pvnames", **kargs)  
    
    if kargs.pop('do_return', False):
        return pvnames

      
#def report_pvs(pattern='*', regex='*', limit=1000, **kargs):#this does not work
def report_pvs(**kargs):  
    '''Report pvs (number of pvs <= 'limit') based on 'pattern' and 'regex'. 
    See the function 'report' (type help(aa.report)) for all keyword arguments.'''
    return report('search', pattern='*', regex='*', limit=1000, **kargs)     


def report_all_pvs(**kargs):
    '''Report all pvs in the Archiver. 
    See the function 'report' (type help(aa.report)) for all keyword arguments.'''
    return report('search', pattern="*", regex="*", limit=-1, **kargs)
   
    
def report_pvs_from_file(**kargs):
    '''Report pvs which are listed as one column in a file. 
    See the function 'report' (type help(aa.report)) for all keyword arguments.'''
    return report("pvs from file", filename='pvlist.txt', **kargs)   
    
    
def report_waveform_pvs(**kargs):
    '''Report waveform PVs that are currently being archived. 
    See the function 'report' (type help(aa.report)) for all keyword arguments.'''
    return report(report_type='waveform', log_file_info=True, **kargs)


def report_storage_rate(**kargs):
    '''Report PVs sorted by descending storage rate. 
    See the function 'report' (type help(aa.report)) for all keyword arguments.'''
    return report(report_type='storage rate', sort=False, **kargs) 


def report_never_connected_pvs(**kargs):
    '''Report never connected pvs, as "PV's that may not exist" on the web. 
    See the function 'report' (type help(aa.report)) for all keyword arguments.'''
    return report(report_type='never connected', **kargs)
 
        
def report_currently_disconnected_pvs(**kargs):
    '''Report currently disconnected pvs, meaning they used to be connected.
    See the function 'report' (type help(aa.report)) for all keyword arguments.'''
    return report(report_type='currently disconnected', **kargs)


def report_paused_pvs(**kargs):
    '''Report currently paused pvs. 
    See the function 'report' (type help(aa.report)) for all keyword arguments.'''
    return report(report_type='paused', **kargs)
        
        
def _get_authentication():
    try: 
        userID = os.popen('whoami').read()[:-1] 
        if userID not in aaconfig_dict["Superusers"]["Account"]:
            print("You do not have permission to do this kind of action on AA")
            sys.exit("Please exit python/ipython shell if the shell does not exit \
by itself. Ask for permission to work on Archiver, then try again.")
    except KeyError:
        pass # no authentication if no aaconfig_dict["Superusers"]["*"]


def _action(pvnames_src=None, act="unknown"):
    '''perform the action 'act' (abort, pause, resume) on pvs
    pvnames_src(source where we get pvnames): 
    1) optional: default is None; 3 actions supported: abort, pause, resume;
    2) a list of pv names: i.e. ['pv1', 'pv2'];
    3) filename: i.e. 'pause_pvs.txt', pv names should be listed as one column
    '''
    _get_authentication()
    
    if pvnames_src is None:
        if act == 'resume':  # resume paused pvs
            pvnames = report_paused_pvs(do_return=True)
        elif act == 'pause': # pause currently disconnected pvs
            pvnames = report_currently_disconnected_pvs(do_return=True);
        elif act == 'abort': # abort never connected pvs
            pvnames = report_never_connected_pvs(do_return=True)
    elif isinstance(pvnames_src, list):
        pvnames = pvnames_src
    else:
        pvnames = get_pvnames_from_file(pvnames_src)
    
    if pvnames_src is not None:
        pvnames = _get_pvnames(pvnames) # sort pv names ... 
    
    if not pvnames:
        return 
        
    answer = raw_input("Do you really wanna %s those PVs? Type yes or no: "%act)
    if answer.upper() != "YES":
        print("Quit. Nothing done.")
        return 
        
    results = []
    valid_pvnames = []
    for pvname in pvnames:
        if act == 'abort':
            result = archiver.abort_pv(pvname) 
        elif act == 'pause':
            result = archiver.pause_pv(pvname) 
        elif act == 'resume':
            result = archiver.resume_pv(pvname)  
                  
        results.append(result)
        try:
            if result['status'] == 'ok':
                print("Successfully {}ed {}.".format(act, pvname))
                valid_pvnames.append(pvname)
        except:
            print("{} is already done or it is not in AA.".format(pvname))
            
    _log(results, act+"_pv details")
    _log(valid_pvnames, act+"ed pvnames")
    
    
def abort_pvs(pvnames_src=None):
    '''Abort each pv in 'pvnames_src' if permission is allowed.
    pvnames_src(source where we get pvnames): 
    1) default is None: pvnames are never connected PVs;
    2) a list of pv names: i.e. ['pv1', 'pv2'];
    3) filename: i.e. 'pause_pvs.txt', pv names should be listed as one column'''
    _action(pvnames_src=pvnames_src, act='abort')


def pause_pvs(pvnames_src=None):
    '''Pause each pv in 'pvnames_src' if permission is allowed.
    pvnames_src(source where we get pvnames): 
    1) default is None: pvnames are currently disconnected PVs;
    2) a list of pv names: i.e. ['pv1', 'pv2'];
    3) filename: i.e. 'pause_pvs.txt', pv names should be listed as one column'''
    _action(pvnames_src=pvnames_src, act='pause') 

def resume_pvs(pvnames_src=None):
    '''resume each pv in 'pvnames_src' if permission is allowed.
    pvnames_src(source where we get pvnames): 
    1) default is None: pvnames are currently paused PVs;
    2) a list of pv names: i.e. ['pv1', 'pv2'];
    3) filename: i.e. 'pause_pvs.txt', pv names should be listed as one column'''
    _action(pvnames_src=pvnames_src, act='resume') 
