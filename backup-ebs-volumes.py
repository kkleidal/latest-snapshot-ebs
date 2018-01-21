# Backup all in-use volumes in all regions

import boto3
import time

REGION = "us-east-2"

def lambda_handler(event, context):
    ec2 = boto3.client('ec2')
    
    # Get list of regions
    regions = ec2.describe_regions().get('Regions',[] )

    region = next(region for region in regions if region['RegionName'] == REGION)
    print("Checking region %s " % region['RegionName'])
    reg=region['RegionName']

    # Connect to region
    ec2 = boto3.client('ec2', region_name=reg)

    # Get all in-use volumes in all regions  
    result = ec2.describe_volumes( Filters=[{'Name': 'status', 'Values': ['in-use']}])
    
    for volume in result['Volumes']:
        print("Backing up %s in %s" % (volume['VolumeId'], volume['AvailabilityZone']))
        # Create snapshot
        result = ec2.create_snapshot(VolumeId=volume['VolumeId'],Description='Created by Lambda backup function ebs-snapshots')
    
        # Get snapshot resource 
        ec2resource = boto3.resource('ec2', region_name=reg)
        snapshot = ec2resource.Snapshot(result['SnapshotId'])
    
        volumename = 'N/A'
    
        # Find name tag for volume if it exists
        if 'Tags' in volume:
            for tags in volume['Tags']:
                if tags["Key"] == 'Name':
                    volumename = tags["Value"]
    
        # Add volume name to snapshot for easier identification
        snapshot.create_tags(Tags=[{'Key': 'Name','Value': volumename}])

        snapshot.reload()
        while snapshot.state == 'pending':
            time.sleep(1)
            print("Snapshot %s of %s is in progress, sleeping..." % \
                    (snapshot.snapshot_id, snapshot.volume_id))
            snapshot.reload()
        if snapshot.state == 'completed':
            print("Snapshot %s of %s finished successfully." % \
                    (snapshot.snapshot_id, snapshot.volume_id))
            print("Removing old snapshots.")

            for old_snapshot in ec2.describe_snapshots(Filters=[dict(
                Name='volume-id',
                Values=[volume['VolumeId']],
            )])['Snapshots']:
                if old_snapshot['SnapshotId'] != snapshot.snapshot_id:
                    sid = old_snapshot['SnapshotId']
                    print("Delete %s" % sid)
                    old_snapshot = ec2resource.Snapshot(sid)
                    old_snapshot.delete()
        else:
            print("Snapshot %s of %s failed with status %s." % \
                    (snapshot.snapshot_id, snapshot.volume_id, snapshot.state))

if __name__ == "__main__":
    lambda_handler(None, None)
