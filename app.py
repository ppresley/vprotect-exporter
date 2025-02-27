from flask import Flask, Response
from prometheus_client import Gauge, CollectorRegistry, generate_latest
import requests
import logging
from urllib3.exceptions import InsecureRequestWarning
from datetime import datetime
import json

# Initialize Flask app
app = Flask(__name__)

# Configure logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress SSL warnings
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Define Prometheus registry
registry = CollectorRegistry()

# Define VM metrics
vprotect_vm_info = Gauge(
    'vprotect_vm_info',
    'VM details and backup status',
    ['vm_name', 'guid', 'restore_status', 'present', 'last_successful_full_backup_size', 'last_successful_full_backup', 'backup_up_to_date'],
    registry=registry
)

# Define Schedule metrics
vprotect_vm_schedules = Gauge(
    'vprotect_vm_schedule_info',
    'VM Schedule details',
    ['active', 'backupType', 'lastRun', 'name', 'type'],
    registry=registry
)

# Define Task metrics
vprotect_task_info = Gauge(
    'vprotect_task_info',
    'Task details and status',
    ['node', 'guid', 'originEntity', 'powerOnAfterRestore', 'priority', 'progress', 'state', 'type', 'windowStart', 'windowEnd', 'task_duration', 'backupDestination', 'protectedEntity', 'backupType', 'hypervisor'],
    registry=registry
)

# Define VM Backup metrics
vprotect_vm_backup_info_gauge = Gauge(
    'vm_backup_info',
    'VM Backup details',
    ['active', 'autoAssignMode', 'backupRetryCount', 'name', 'priority', 'ruleBackupDestinations'],
    registry=registry
)

# Define Hypervisor metrics
vprotect_hypervisor_info = Gauge(
    'vprotect_hypervisor_info',
    'HYPERVISOR details',
    ['cluster', 'guid', 'host', 'licenseCovered', 'type', 'user', 'vmCount'],
    registry=registry
)

# Define node metrics
vprotect_node_info = Gauge(
    'vprotect_node_info',
    'Node details',
    ['name', 'guid', 'lastSeen', 'nodeIP', 'totalSpace', 'usedSpace', 'state', 'version'],
    registry=registry
)

# API configuration
API_BASE_URL = 'https://192.168.70.108/api'
LOGIN_URL = f'{API_BASE_URL}/session/login'
USERNAME = 'prometheus'
PASSWORD = '7e@YoP_2Se6-'
VM_URL = f'{API_BASE_URL}/virtual-machines'
SCHEDULES_URL = f'{API_BASE_URL}/schedules'
TASKS_URL = f'{API_BASE_URL}/tasks'
VM_BACKUP_URL = f'{API_BASE_URL}/policies/vm-backup'
HYPERVISOR_URL = f'{API_BASE_URL}/hypervisors'
NODE_URL = f'{API_BASE_URL}/nodes'

# Create a session with SSL verification disabled
session = requests.Session()
session.verify = False

def get_auth_token():
    """Authenticate and return session cookie."""
    try:
        response = session.post(
            LOGIN_URL,
            json={"login": USERNAME, "password": PASSWORD},
            timeout=30
        )
        response.raise_for_status()
        logger.info("Authentication successful")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Authentication failed: {e}")
        return False

def fetch_vms():
    """Fetch VM data from API."""
    try:
        logger.info(f"Fetching data from {VM_URL}")
        response = session.get(VM_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
        logger.debug(f"Raw API response: {json.dumps(data, indent=2)}")
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch VM data: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON response: {e}")
        return None

def fetch_schedules():
    """Fetch Schedule data from API."""
    try:
        logger.info(f"Fetching data from {SCHEDULES_URL}")
        response = session.get(SCHEDULES_URL, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch Schedule data: {e}")
        return None

def fetch_tasks():
    """Fetch Task data from API."""
    try:
        logger.info(f"Fetching data from {TASKS_URL}")
        response = session.get(TASKS_URL, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch Task data: {e}")
        return None

def fetch_vm_backups():
    """Fetch VM Backup data from API."""
    try:
        logger.info(f"Fetching data from {VM_BACKUP_URL}")
        response = session.get(VM_BACKUP_URL, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch VM Backup data: {e}")
        return None

def fetch_hypervisor_details():
    """Fetch Hypervisor data from API."""
    try:
        logger.info(f"Fetching data from {HYPERVISOR_URL}")
        response = session.get(HYPERVISOR_URL, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch Hypervisor data: {e}")
        return None

def fetch_node_details():
    """Fetch Node data from API."""
    try:
        logger.info(f"Fetching data from {NODE_URL}")
        response = session.get(NODE_URL, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch Node data: {e}")
        return None

def update_vm_metrics():
    """Update Prometheus metrics with VM data."""
    try:
        # Clear existing metrics first
        vprotect_vm_info._metrics.clear()

        vms_data = fetch_vms()
        if vms_data is None:
            logger.error("No VM data received")
            return

        logger.debug(f"Type of vms_data: {type(vms_data)}")
        logger.debug(f"Content of vms_data: {json.dumps(vms_data, indent=2)}")

        # Handle the response based on its type
        if isinstance(vms_data, list):
            vms = vms_data
        elif isinstance(vms_data, dict):
            vms = vms_data.get('members', [])
            if not vms:
                vms = [vms_data]  # If it's a single VM object
        else:
            logger.error(f"Unexpected data type received: {type(vms_data)}")
            return

        logger.info(f"Processing {len(vms)} VMs")

        for vm in vms:
            try:
                logger.debug(f"Processing VM data: {json.dumps(vm, indent=2)}")

                # Extract VM data with safe defaults
                vm_name = str(vm.get('name', 'Unknown'))
                guid = str(vm.get('guid', 'Unknown'))
                restore_status = str(vm.get('restoreStatus', 'Unknown'))
                present = str(vm.get('present', False))
                last_successful_full_backup_size = str(vm.get('lastSuccessfulFullBackupSize', 0))
                last_successful_full_backup = str(vm.get('lastSuccessfulFullBackup', {}).get('name', 'Unknown')).split(' - ')[-1]
                backup_up_to_date = str(vm.get('backupUpToDate', False))

                logger.debug(f"Extracted VM data for {vm_name}:")
                logger.debug(f"Extracted VM data for {guid}:")
                logger.debug(f"  restore_status: {restore_status}")
                logger.debug(f"  present: {present}")
                logger.debug(f"  last_successful_full_backup_size: {last_successful_full_backup_size}")
                logger.debug(f"  last_successful_full_backup: {last_successful_full_backup}")
                logger.debug(f"  backup_up_to_date: {backup_up_to_date}")

                # Update metrics
                vprotect_vm_info.labels(
                    vm_name=vm_name,
                    guid=guid,
                    restore_status=restore_status,
                    present=present,
                    last_successful_full_backup_size=last_successful_full_backup_size,
                    last_successful_full_backup=last_successful_full_backup,
                    backup_up_to_date=backup_up_to_date
                ).set(1)

                logger.info(f"Successfully updated metrics for VM: {vm_name}")
            except Exception as e:
                logger.error(f"Error processing VM {vm.get('name', 'Unknown')}: {str(e)}")
                logger.exception("Full traceback:")
                continue

    except Exception as e:
        logger.error(f"Error updating VM metrics: {str(e)}")
        logger.exception("Full traceback:")

def update_schedule_metrics():
    """Update Prometheus metrics with Schedule data."""
    try:
        vprotect_vm_schedules._metrics.clear()
        schedules_data = fetch_schedules()
        if not schedules_data:
            logger.error("No Schedule data received")
            return

        schedules = schedules_data.get('members', schedules_data) if isinstance(schedules_data, dict) else schedules_data
        for schedule in schedules:
            try:
                vprotect_vm_schedules.labels(
                    active=str(schedule.get('active', False)),
                    backupType=str(schedule.get('backupType',{}).get('name', {})),
                    lastRun=str(schedule.get('lastRun', 'Never')),
                    name=schedule.get('name', 'Unknown'),
                    type=str(schedule.get('type',{}).get('description', {}))
                ).set(1)
            except Exception as e:
                logger.error(f"Error processing Schedule {schedule.get('name', 'Unknown')}: {str(e)}")
                continue
    except Exception as e:
        logger.error(f"Error updating Schedule metrics: {str(e)}")

def update_task_metrics():
    """Update Prometheus metrics with Task data."""
    try:
        vprotect_task_info._metrics.clear()
        tasks_data = fetch_tasks()
        if not tasks_data:
            logger.error("No Task data received")
            return

        tasks = tasks_data.get('members', tasks_data) if isinstance(tasks_data, dict) else tasks_data
        for task in tasks:
            try:
                guid = task.get('guid', 'Unknown')
                window_start = task.get('windowStart', 0)
                window_end = task.get('windowEnd', 0)
                task_duration = str(int(window_end) - int(window_start)) if window_start and window_end else 'Unknown'

                vprotect_task_info.labels(
                    node=str(task.get('node', {}).get('name', 'Unknown')),
                    guid=str(guid),
                    originEntity=str(task.get('originEntity', {}).get('type', {}).get('name', 'Unknown')),
                    powerOnAfterRestore=str(task.get('powerOnAfterRestore', False)),
                    priority=str(task.get('priority', 'Unknown')),
                    progress=str(task.get('progress', 'Unknown')),
                    state=str(task.get('state', {}).get('name', 'Unknown')),
                    hypervisor=str(task.get('hypervisor', {}).get('name', 'Unknown')),
                    type=str(task.get('type', {}).get('name', 'Unknown')),
                    windowStart=str(window_start),
                    windowEnd=str(window_end),
                    task_duration=task_duration,
                    backupDestination=str(task.get('backupDestination', {}).get('name', 'Unknown')),
                    protectedEntity=str(task.get('protectedEntity', {}).get('name', 'Unknown')),
                    backupType=str(task.get('backupType', {}).get('name', 'Unknown'))
                ).set(1)

                logger.info(f"Updated metrics for Task: {guid}")
            except Exception as e:
                logger.error(f"Error processing Task {task.get('guid', 'Unknown')}: {str(e)}")
                continue
    except Exception as e:
        logger.error(f"Error updating Task metrics: {str(e)}")

def update_vm_backup_metrics():
    """Update Prometheus metrics with VM Backup data."""
    try:
        logger.info("Updating VM Backup metrics...")
        vm_backup_info_gauge._metrics.clear()
        vm_backup_data = fetch_vm_backups()
        if not vm_backup_data:
            logger.error("No VM Backup data received")
            return
        backups = vm_backup_data.get('members', vm_backup_data) if isinstance(vm_backup_data, dict) else vm_backup_data

        logger.info(f"Processing {len(backups)} VM backups")

        for backup in backups:
            try:
                rule_destinations = backup.get('ruleBackupDestinations', [])
                if rule_destinations and isinstance(rule_destinations, list):
                    rule_backup_destination = rule_destinations[0].get('backupDestination', {}).get('name', 'Unknown')
                else:
                    rule_backup_destination = 'Unknown'

                vm_backup_info_gauge.labels(
                    active=str(backup.get('active', 'Unknown')),
                    autoAssignMode=str(backup.get('autoAssignMode', {}).get('name', 'Unknown')),
                    backupRetryCount=str(backup.get('backupRetryCount', 'Unknown')),
                    name=str(backup.get('name', 'Unknown')),
                    priority=str(backup.get('priority', 'Unknown')),
                    ruleBackupDestinations=rule_backup_destination
                ).set(1)
                logger.info(f"Successfully updated backup metrics for {backup.get('name', 'Unknown')}")
            except Exception as e:
                logger.error(f"Error processing VM Backup {backup.get('guid', 'Unknown')}: {str(e)}")
                continue
    except Exception as e:
        logger.error(f"Error updating VM Backup metrics: {str(e)}")

def update_hypervisor_metrics():
    """Update Prometheus metrics with Hypervisor data."""
    try:
        logger.info("Updating Hypervisor metrics...")
        vprotect_hypervisor_info._metrics.clear()
        hypervisor_data = fetch_hypervisor_details()
        if not hypervisor_data:
            logger.error("No Hypervisor data received")
            return
        hypervisors = hypervisor_data.get('members', hypervisor_data) if isinstance(hypervisor_data, dict) else hypervisor_data

        logger.info(f"Processing {len(hypervisors)}")

        for hypervisor in hypervisors:
            try:
                vprotect_hypervisor_info.labels(
                    cluster=str(hypervisor.get('cluster', {}).get('name', 'Unknown')),
                    guid=str(hypervisor.get('guid', 'Unknown')),
                    host=str(hypervisor.get('host', 'Unknown')),
                    licenseCovered =str(hypervisor.get('licenseCovered', 'Unknown')),
                    type=str(hypervisor.get('type', {}).get('name', 'Unknown')),
                    user=str(hypervisor.get('user', 'Unknown')),
                    vmCount=str(hypervisor.get('vmCount', 'Unknown'))
                ).set(1)
                logger.info(f"Successfully updated hypervisor metrics for {hypervisor.get('cluster', 'Unknown')}")
            except Exception as e:
                logger.error(f"Error processing Hypervisor {hypervisor.get('guid', 'Unknown')}: {str(e)}")
                continue
    except Exception as e:
        logger.error(f"Error updating Hypervisor metrics: {str(e)}")

def update_node_metrics():
    """Update Prometheus metrics with Node data."""
    try:
        logger.info("Updating Node metrics...")
        vprotect_node_info._metrics.clear()
        node_data = fetch_node_details()
        if not node_data:
            logger.error("No Node data received")
            return
        nodes = node_data.get('members', node_data) if isinstance(node_data, dict) else node_data

        logger.info(f"Processing {len(nodes)}")

        for node in nodes:
            try:
                vprotect_node_info.labels(
                    name=str(node.get('name', 'Unknown')),
                    guid=str(node.get('guid', 'Unknown')),
                    lastSeen=str(node.get('lastSeen', 'Unknown')),
                    nodeIP=str(node.get('nodeIP', 'Unknown')),
                    totalSpace=str(node.get('stagingSpace', {}).get('totalSpace', 'Unknown')),
                    usedSpace=str(node.get('stagingSpace', {}).get('usedSpace', 'Unknown')),
                    state=str(node.get('state', {}).get('name', 'Unknown')),
                    version=str(node.get('version', 'Unknown'))
                ).set(1)
                logger.info(f"Successfully updated node metrics for {node.get('name', 'Unknown')}")
            except Exception as e:
                logger.error(f"Error processing Node {node.get('guid', 'Unknown')}: {str(e)}")
                continue
    except Exception as e:
        logger.error(f"Error updating Node metrics: {str(e)}")

@app.route('/metrics')
def metrics():
    """Expose Prometheus metrics."""
    if not get_auth_token():
        logger.error("Failed to authenticate")
        return Response("Authentication failed", status=500)

    update_vm_metrics()
    update_schedule_metrics()
    update_task_metrics()
    update_vm_backup_metrics()
    update_hypervisor_metrics()
    update_node_metrics()
    return Response(generate_latest(registry), mimetype='text/plain')

@app.route('/')
def home():
    return "vProtect Exporter is running"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9176)
