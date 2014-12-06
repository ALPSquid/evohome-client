import json

from zone import Zone
from hotwater import HotWater
from base import EvohomeBase, EvohomeClientInvalidPostData

class ControlSystem(EvohomeBase):

    def __init__(self, client, location, gateway, data=None):
        super(ControlSystem, self).__init__()
        self.client = client
        self.location = location
        self.gateway = gateway
        self._zones = []
        self.zones = {}
        self.zones_by_id = {}
        self.hotwater = None

        if data is not None:

            local_data = dict(data)
            del local_data['zones']

            self.__dict__.update(local_data)

            for i, z_data in enumerate(data['zones']):
                zone = Zone(client, location, z_data)
                self._zones.append(zone)
                self.zones[zone.name] = zone
                self.zones_by_id[zone.zoneId] = zone

            if 'dhw' in data:
                self.hotwater = HotWater(client, data['dhw'])

    def _set_status(self, mode, until=None):

        headers = dict(self.headers)
        headers['Content-Type'] = 'application/json'

        if until is None:
            data = {"SystemMode":mode,"TimeUntil":None,"Permanent":True}
        else:
            data = {"SystemMode":mode,"TimeUntil":"%sT00:00:00Z" % until.strftime('%Y-%m-%d'),"Permanent":False}
        r = requests.put('https://rs.alarmnet.com:443/TotalConnectComfort/WebAPI/emea/api/v1/temperatureControlSystem/%s/mode' % self.systemId, data=json.dumps(data), headers=headers)

    def set_status_normal(self):
        self._set_status(0)

    def set_status_custom(self, until=None):
        self._set_status(6, until)

    def set_status_eco(self, until=None):
        self._set_status(2, until)

    def set_status_away(self, until=None):
        self._set_status(3, until)

    def set_status_dayoff(self, until=None):
        self._set_status(4, until)

    def set_status_heatingoff(self, until=None):
        self._set_status(1, until)

    def temperatures(self):
        status = self.location.status()

        if self.hotwater:
            yield {'thermostat': 'DOMESTIC_HOT_WATER',
                    'id': self.hotwater.dhwId,
                    'name': '',
                    'temp': self.hotwater.temperatureStatus['temperature'],
                    'setpoint': ''
                   }

        for zone in self._zones:
            yield {'thermostat': 'EMEA_ZONE',
                    'id': zone.zoneId,
                    'name': zone.name,
                    'temp': zone.temperatureStatus['temperature'],
                    'setpoint': zone.heatSetpointStatus['targetTemperature'],
                    'overridden': self.zones[zone.name].is_overridden()
                   }

    def zone_temperature(self, zone_id):
        zone = self.zones_by_id[zone_id]
        return {'thermostat': 'EMEA_ZONE',
                'id': zone.zoneId,
                'name': zone.name,
                'temp': zone.temperatureStatus['temperature'],
                'setpoint': zone.heatSetpointStatus['targetTemperature']
               }

    def get_zone_id(self, zone_name):
        """
        Convenience function
        """
        return self.zones[zone_name].zoneId

    def zone_schedule(self, zone_id):
        """
        Creates a dictionary of a zones weekly schedule
        :param zone_id: ID of the zone to query
        :return: A dictionary in the format:
                    {day: {time: temp}}
        """
        schedule = self.zones_by_id[zone_id].schedule()["DailySchedules"]
        week_sched = {}
        for day in schedule:
            day_sched = {}
            for switch in day["Switchpoints"]:
                time = switch["TimeOfDay"]
                temp = switch["TargetTemperature"]
                day_sched[time] = temp
            week_sched[day["DayOfWeek"]] = day_sched
        return week_sched

    def zone_schedules_backup(self, filename):
        print("Backing up zone schedule to: %s" % (filename))

        schedules = {}
        
        if self.hotwater:
            print("Retrieving DHW schedule: %s" % self.hotwater.zoneId)
            s = self.hotwater.schedule()
            schedules[self.hotwater.zoneId] = {'name': 'Domestic Hot Water', 'schedule': s}
        
        for z in self._zones:
            zone_id = z.zoneId
            name = z.name
            print("Retrieving zone schedule: %s - %s" % (zone_id, name))
            s = z.schedule()
            schedules[zone_id] = {'name': name, 'schedule': s}
            
        schedule_db = json.dumps(schedules, indent=4)

        with open(filename, 'w') as f:
            f.write(schedule_db)

        print("Backed up zone schedule to: %s" % filename)

    def zone_schedules_restore(self, filename):
        print("Restoring zone schedules from: %s" % filename)
        with open(filename, 'r') as f:
            schedule_db = f.read()
            schedules = json.loads(schedule_db)
            for zone_id, zone_schedule in schedules.iteritems():
                
                name = zone_schedule['name']
                zone_info = zone_schedule['schedule']
                print("Restoring schedule for: %s - %s" % (zone_id, name))
                
                if self.hotwater and self.hotwater.zoneId==zone_id:
                    self.hotwater.set_schedule(json.dumps(zone_info))
                else:
                    self.zones_by_id[zone_id].set_schedule(json.dumps(zone_info))
        print("Restored zone schedules from: %s" % filename)
