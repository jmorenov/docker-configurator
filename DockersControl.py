#!/usr/bin/python

#--start <docker_name>
#--build <docker_name>
#--build-all
#--get-dockers
#--stop <docker_name>
#--start-all
#--stop-all
#--restart <docker_name>
#--restart-all

import sys, getopt
import json
import subprocess
import os
from __future__ import print_function

CONFIG_FILE = 'DockersConfig.json'

def readConfigFile(file):
    try:
        jdata = open(file)
        data = json.load(jdata)
        jdata.close()
    except IOError:
        print ('ERROR: Configuration File not found')
        sys.exit(2)
    except OSError as err:
        print ('ERROR: OS error: {0}'.format(err))
        sys.exit(2)
    except ValueError:
        print ('ERROR: Could not read the config file (', file, ')')
        sys.exit(2)
    except:
        print ('ERROR: Unexpected error:', sys.exc_info()[0])
        sys.exit(2)
    else:
        return data

def getDocker(configFile, dockerName):
    try:
        dockers = readConfigFile(configFile)['dockers']
    except KeyError:
        print ('ERROR: Bad configuration file format')
        sys.exit(2)
    else:
        try:
            docker = dockers[dockerName]
            docker['name'] = dockerName
        except KeyError:
            print ('[ERROR] Docker name', dockerName, 'not found')
            sys.exit(2)
        else:
            return docker

def getNetwork(configFile):
    try:
        networkConfig = readConfigFile(configFile)['defaultNetwork']
    except KeyError:
        print ('[ERROR] Bad configuration file format')
        sys.exit(2)
    else:
        return networkConfig

def runCommand(command, stdin=None, stdoutConsole=False):
    try:
        subprocess.Popen('docker', stdout=subprocess.PIPE)
    except OSError as e:
        if e.errno == os.errno.ENOENT:
            print ('ERROR: Docker should be installed')
            os._exit(2)
    else:
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=stdin)

        if stdoutConsole:
            for line in iter(proc.stdout.readline, ''):
                sys.stdout.write(line)
		
        out, err = proc.communicate()
        returnCode = proc.returncode

        return out, err, returnCode

def isDockerRunning(dockerName):
    out, err, returnCode = runCommand('docker ps --filter "name=' + dockerName + '" | grep -w ' + dockerName + ' | awk \'{print $1}\'')

    return len(out) != 0

def createNetwork(networkConfig):
    #subnet = '--subnet=' + str(networkConfig['subnet'])
    name = str(networkConfig['name'])

    out, err, returnCode = runCommand('docker network ls --filter "name=' + name + '" | grep -w ' + name + '')

    if len(out) == 0:
        '''print ('Creating network ' + name
        out, err, returnCode = runCommand(['docker', 'network', 'create', subnet, name]))'''
        print ('[ERROR] Network '  + name + ' not exists')
        os._exit(2)

def buildDocker(imageName, imagePath):
    out, err, returnCode = runCommand('docker build ' + imagePath + ' -t ' + imageName, stdoutConsole=True)

    if returnCode == 1:
        print (err)
        os._exit(1)

def getValueOfConfigKey(dockerConfig, key, isMandatory = False):
    if key in dockerConfig:
        value = dockerConfig[key]
        if isinstance(value, bool) or isinstance(value, list) or isinstance(value, dict):
            return dockerConfig[key]
        else:
            return str(dockerConfig[key])
    elif isMandatory:
        print ('ERROR: Key config ' + key + ' not found and is mandatory')
        os._exit(1)
    else:
        return False

def runDocker(dockerConfig, defaultNetworkName):
    command = 'docker run'

    privileged = getValueOfConfigKey(dockerConfig, 'privileged')

    if privileged:
        command += ' --privileged=true'

    ports = getValueOfConfigKey(dockerConfig, 'ports')
    if ports and isinstance(ports, list) and len(ports) > 0:
        for port in ports:
            serverPort = getValueOfConfigKey(port, 'serverPort', True)
            dockerPort = getValueOfConfigKey(port, 'dockerPort', True)
            command += ' -p '
            command += (serverPort + ':' + dockerPort)

    name = getValueOfConfigKey(dockerConfig, 'name')

    command += ' --name '
    command += name

    net = getValueOfConfigKey(dockerConfig, 'net') or defaultNetworkName
    if net:
        ip = getValueOfConfigKey(dockerConfig, 'ip', True)

        command += (' --net ' + net + ' --ip ' + ip)

    link = getValueOfConfigKey(dockerConfig, 'link')
    if link:
        command += ' --link ' + link

    mountVolumes = getValueOfConfigKey(dockerConfig, 'mountVolumes')
    if mountVolumes and isinstance(mountVolumes, list) and len(mountVolumes) > 0:
        for volume in mountVolumes:
            command += ' -v '
            localVolume = getValueOfConfigKey(volume, 'localVolume', True)
            dockerVolume = getValueOfConfigKey(volume, 'dockerVolume', True)
            command += (localVolume + ':' + dockerVolume)

    variables = getValueOfConfigKey(dockerConfig, 'variables', False)
    if variables:
        for key in variables.keys():
            value = variables[key]
            command += ' -e ' + key + '=' + value

    image = getValueOfConfigKey(dockerConfig, 'image', True)

    command += ' -d '
    command += image

    needBuild = getValueOfConfigKey(dockerConfig, 'needBuild')

    if needBuild:
        imagePath = getValueOfConfigKey(dockerConfig, 'imagePath', True)

        endInput = False

        while endInput == False:
            build = raw_input('Build the docker image (Y/N)?: ')

            if build == 'Y':
                endInput = True
                build = True
            elif build == 'N':
                endInput = True
                build = False

        if build:
            imageName = getValueOfConfigKey(dockerConfig, 'image', True)
            buildDocker(imageName, imagePath)

    out, err, returnCode = runCommand(command)

    if returnCode != 0 or len(err) != 0:
        print (out)
        print ('[ERROR] ' + err)
        os._exit(1)
    elif isDockerRunning(name) == False:
        stopADockerByName(name)
        print ('[ERROR] Something failed. Docker is not running')
        os._exit(1)
    else:
        print ('[OK] Docker ' + name + ' running')

# "Interface" functions
def startADocker(configFile, dockerName):
    if isDockerRunning(dockerName):
        print ('[INFO] Docker ' + dockerName + ' is already running')
    else:
        dockerConfig = getDocker(configFile, dockerName)
        networkConfig = getNetwork(configFile)
        try:
            createNetwork(networkConfig)
            runDocker(dockerConfig, networkConfig['name'])
        except:
            print ('[ERROR] Unexpected error:', sys.exc_info()[0])
            sys.exit(2)

def startAll(configFileName):
    configFile = readConfigFile(configFileName)
    dockers = configFile['dockers']

    for docker in dockers.keys():
        startADocker(configFileName, docker)

def stopAll(configFileName):
    configFile = readConfigFile(configFileName)
    dockers = configFile['dockers']

    for docker in dockers.keys():
        stopADockerByName(docker)

def restartAll(configFileName):
    configFile = readConfigFile(configFileName)
    dockers = configFile['dockers']

    for docker in dockers.keys():
        restartADocker(configFileName, docker)

def restartADocker(configFile, dockerName):
    stopADocker(dockerName)
    startADocker(configFile, dockerName)

def stopADocker(dockerName):
    stopADockerByName(dockerName)

def stopADockerByName(dockerName):
    out, err, returnCode = runCommand('docker ps -a --filter "name=' + dockerName + '" | grep -w ' + dockerName + ' | awk \'{print $1}\'')

    if len(out) != 0:
        runCommand('docker stop ' + dockerName)
        runCommand('docker kill ' + dockerName)
        out, err, returnCode = runCommand('docker rm ' + dockerName)

        if  len(err) != 0:
            print ('[ERROR] Docker: ' + dockerName + '')
        else:
            print ('[OK] Docker: ' + dockerName + ' stopped')
    else:
        print ('[ERROR] Docker: ' + dockerName + ' is already stopped')

def stopADockerByImage(dockerImage):
    out, err, returnCode = runCommand('docker ps -a --filter "ancestor=' + dockerImage + '" | grep -w ' + dockerImage + ' | awk \'{print $1}\'')

    if len(out) != 0:
        out = out.split('\n')

        for id in out:
            if id:
                runCommand('docker stop ' + id)
                runCommand('docker kill ' + id)
                out, err, returnCode = runCommand('docker rm ' + id)

                if  len(err) != 0:
                    print ('[ERROR] Docker image: ' + dockerImage + ' with ID' + id)
                    sys.exit(2)

        print ('[OK] Docker image: ' + dockerImage + ' stopped')

def getDockers(configFile):
    data = readConfigFile(configFile)
    for dockerName in data['dockers'].keys(): print (dockerName)

def main(argv):
    configFile = CONFIG_FILE
    try:
        opts, args = getopt.getopt(argv,'h',['help', 'start-all','config-file=',
                                             'get-dockers', 'start=', 'stop=',
                                             'stop-by-name=', 'stop-by-image=',
                                             'restart=', 'stop-all', 'restart-all', 'default'])
    except getopt.GetoptError:
        print ('Error: try DockersControl.py --help/-h')
        sys.exit(2)

    arguments = []
    values = []
    for opt, arg in opts:
        arguments.append(opt)
        values.append(arg)

    if arguments == []:
        print ('Error: try DockersControl.py --help/-h')
        sys.exit(2)

    if '-h' in arguments or '--help' in arguments:
        print ('Commands:')
        print ('--start-all')
        print ('--stop-all')
        print ('--restart-all')
        print ('--start <docker name>')
        print ('--stop <docker name>')
        print ('--stop-by-name <docker name>')
        print ('--stop-by-image <docker image>')
        print ('--restart <docker name>')
        print ('--get-dockers')
        sys.exit()

    if '--config-file' in arguments:
        configFile = values[arguments.index('--config-file')]

    if '--start-all' in arguments:
        startAll(configFile)
    elif '--stop-all' in arguments:
        stopAll(configFile)
    elif '--restart-all' in arguments:
        restartAll(configFile)
    elif '--restart' in arguments:
        restartADocker(configFile, values[arguments.index('--restart')])
    elif '--get-dockers' in arguments:
        getDockers(configFile)
    elif '--start' in arguments:
        startADocker(configFile, values[arguments.index('--start')])
    elif '--stop' in arguments:
        stopADocker(values[arguments.index('--stop')])
    elif '--stop-by-name' in arguments:
        stopADockerByName(values[arguments.index('--stop-by-name')])
    elif '--stop-by-image' in arguments:
        stopADockerByImage(values[arguments.index('--stop-by-image')])
    else:
        print ('Error: try DockersControl.py --help/-h')
        sys.exit(2)

if __name__ == '__main__':
    main(sys.argv[1:])