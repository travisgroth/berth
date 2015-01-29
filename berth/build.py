"""Handles everything related to the actual build process."""

import time
from os import chmod, path, unlink
from tempfile import NamedTemporaryFile

import berth.utils as utils


def build(config):
    """Run the build part of the configuration."""
    utils.log('Building project.')

    script_path = create_build_script(config['build']['script'])
    script_container_path = '/{}'.format(path.basename(script_path))

    volumes = config['build'].get('volumes', dict())
    volumes[script_path] = script_container_path
    volume_list, binds = utils.convert_volumes_list(volumes)

    docker = utils.docker_client()
    container = docker.create_container(
        image=config['build']['image'],
        command=[script_container_path],
        volumes=volume_list,
    )

    if container['Warnings']:
        utils.log('We got a warning when creating the build container:', err=True, fg='red', bold=True)
        utils.log(str(container['Warnings']), err=True, prefix=False)
        remove_build_script(script_path)
        return False

    utils.debug('Starting build container.')
    start_time = time.time()
    docker.start(container['Id'], binds=binds)
    utils.info('Build container started.')

    exit_code = docker.wait(container['Id'])
    utils.info('The build container has stopped after {:.3} seconds.'.format(time.time() - start_time))

    if exit_code != 0 or utils.get_log_level() > 0:
        utils.debug('Getting output from container.')
        logs = docker.logs(container['Id']).decode('utf-8').rstrip()

        if exit_code != 0:
            utils.log('Build script failed with exit code: {}. Output follows:'.format(exit_code), err=True, fg='red', bold=True)
        else:
            utils.info('Build script output follows:')
        utils.log(logs, err=(exit_code != 0), prefix=False)
    else:
        utils.log('Build succeeded.')

    utils.debug('Removing build container.')
    docker.remove_container(container['Id'])
    utils.info('Removed build container.')

    remove_build_script(script_path)

    return exit_code == 0


def create_build_script(script):
    """Write the build script to a temporary file."""
    utils.debug('Writing build script to temporary file.')
    with NamedTemporaryFile(prefix='berth-build-', suffix='.sh', delete=False, dir='.') as script_file:
        script_file.write(script.encode('utf-8'))
        script_path = script_file.name
    chmod(script_path, 493)  # Add execute permissions: 493 = rwxr-xr-x
    utils.info('Wrote temporary build script to "{}".'.format(script_path))
    return script_path


def remove_build_script(script_path):
    """Remove the temporary build script file."""
    utils.debug('Removing temporary build script at "{}".'.format(script_path))
    unlink(script_path)
    utils.info('Removed temporary build script.')
