# -*- coding: utf-8 -*-

# FOGLAMP_BEGIN
# See: http://foglamp.readthedocs.io/
# FOGLAMP_END

import os
import logging
import uuid
import platform

from aiohttp import web
from foglamp.common import logger
from foglamp.services.core import connect
from foglamp.common.storage_client.payload_builder import PayloadBuilder
from foglamp.services.core import server
from foglamp.common.plugin_discovery import PluginDiscovery
from foglamp.common.common import _FOGLAMP_ROOT, _FOGLAMP_DATA


__author__ = "Ashish Jabble"
__copyright__ = "Copyright (c) 2019 Dianomic Systems Inc."
__license__ = "Apache 2.0"
__version__ = "${VERSION}"

_help = """
    -------------------------------------------------------------------------------
    | PUT             | /foglamp/plugin/{type}/{name}/update                      |
    -------------------------------------------------------------------------------
"""
_logger = logger.setup(__name__, level=logging.INFO)


async def update_plugin(request: web.Request) -> web.Response:
    """ update plugin

    :Example:
        curl -X PUT http://localhost:8081/foglamp/plugins/south/sinusoid/update
        curl -X PUT http://localhost:8081/foglamp/plugins/north/http_north/update
    """
    _type = request.match_info.get('type', None)
    name = request.match_info.get('name', None)
    try:
        # TODO: filter and notification types will be handled in future
        _type = _type.lower()
        if _type not in ['north', 'south']:
            raise ValueError("Invalid plugin type. Must be 'north' or 'south'")

        # Check requested plugin name is installed or not
        installed_plugins = PluginDiscovery.get_plugins_installed(_type, False)
        installed_plugin_name = [p_name["name"] for p_name in installed_plugins]
        if name not in installed_plugin_name:
            raise KeyError("{} plugin is not yet installed. So update is not possible.".format(name))

        # Tracked plugins from asset tracker
        tracked_plugins = await _get_plugin_and_sch_name_from_asset_tracker(_type)
        sch_list = []
        for p in tracked_plugins:
            if name == p['plugin']:
                sch_info = await _get_sch_id_and_enabled_by_name(p['service'])
                if sch_info[0]['enabled'] == 't':
                    status, reason = await server.Server.scheduler.disable_schedule(uuid.UUID(sch_info[0]['id']))
                    if status:
                        _logger.warning("{} {} instance is disabled as {} plugin is updating..".format(p['service'], _type, p['plugin']))
                        sch_list.append(sch_info[0]['id'])
        retcode, msg = update_repo_sources_and_plugin(_type, name)
        if retcode != 0:
            _logger.error("Plugin update failed..{}".format(msg))

        # Restart the services which were disabled before plugin update
        for s in sch_list:
            await server.Server.scheduler.enable_schedule(uuid.UUID(s))

        # TODO: should run as background task
    except KeyError as ex:
        raise web.HTTPNotFound(reason=ex)
    except ValueError as ex:
        raise web.HTTPBadRequest(reason=ex)
    except Exception as ex:
        raise web.HTTPInternalServerError(reason=ex)

    return web.json_response({"message": "Plugin update in process. Wait for few minutes to complete."})


async def _get_plugin_and_sch_name_from_asset_tracker(_type: str) -> list:
    event_name = "Ingest" if _type == "south" else "Egress"
    storage_client = connect.get_storage_async()
    payload = PayloadBuilder().SELECT("plugin", "service").WHERE(['event', '=', event_name]).payload()
    result = await storage_client.query_tbl_with_payload('asset_tracker', payload)
    return result['rows']


async def _get_sch_id_and_enabled_by_name(name) -> list:
    storage_client = connect.get_storage_async()
    payload = PayloadBuilder().SELECT("id", "enabled").WHERE(['schedule_name', '=', name]).payload()
    result = await storage_client.query_tbl_with_payload('schedules', payload)
    return result['rows']


def update_repo_sources_and_plugin(_type:str, name: str) -> tuple:
    # Below check is needed for python plugins
    # For Example: installed_plugin_dir=wind_turbine; package_name=wind-turbine
    if "_" in name:
        name = name.replace("_", "-")

    # For endpoint curl -X GET http://localhost:8081/foglamp/plugins/available we used
    # sudo apt list command internal so package name always returns in lowercase; irrespective of package name defined in the configured repo.
    name = name.lower()
    _platform = platform.platform()
    pkg_mgt = 'yum' if 'centos' in _platform or 'redhat' in _platform else 'apt'
    _PATH = _FOGLAMP_DATA + '/plugins/' if _FOGLAMP_DATA else _FOGLAMP_ROOT + '/data/plugins/'

    stdout_file_path = _PATH + "output.txt"
    if not os.path.exists(_PATH):
        os.makedirs(_PATH)

    cmd = "sudo {} update > {} 2>&1".format(pkg_mgt, stdout_file_path)
    ret_code = os.system(cmd)
    msg = ""
    if ret_code == 0:
        cmd = "sudo {} -y install foglamp-{}-{} > {} 2>&1".format(pkg_mgt, _type, name, stdout_file_path)
        ret_code = os.system(cmd)
        with open("{}".format(stdout_file_path), 'r') as fh:
            for line in fh:
                line = line.rstrip("\n")
                msg += line
    # Remove stdout file
    os.remove(stdout_file_path)

    return ret_code, msg
