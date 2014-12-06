import json
import requests
from datetime import datetime, tzinfo
from base import EvohomeBase, EvohomeClientInvalidPostData

class ZoneBase(EvohomeBase):
    def __init__(self):
        super(ZoneBase, self).__init__()

    def schedule(self):
        r = requests.get('https://rs.alarmnet.com:443/TotalConnectComfort/WebAPI/emea/api/v1/%s/%s/schedule' % (self.zone_type, self.zoneId), headers=self.client.headers)
        # was request ok ?
        r.raise_for_status()
        mapping = [
            ('dailySchedules', 'DailySchedules'),
            ('dayOfWeek', 'DayOfWeek'),
            ('temperature', 'TargetTemperature'),
            ('timeOfDay', 'TimeOfDay'),
            ('switchpoints', 'Switchpoints'),
            ('dhwState', 'DhwState'),
        ]
        j = r.text
        for f, t in mapping:
            j = j.replace(f, t)
            
        d = self._convert(j)
        # change the day name string to a number offset (0 = Monday)
        for day_of_week, schedule in enumerate(d['DailySchedules']):
            schedule['DayOfWeek'] = day_of_week
        return d
        
    def set_schedule(self, zone_info):
        # must only POST json, otherwise server API handler raises exceptions

        try:
            t1 = json.loads(zone_info)
        except:
            raise EvohomeClientInvalidPostData('zone_info must be JSON')

        headers = dict(self.client.headers)
        headers['Content-Type'] = 'application/json'
        r = requests.put('https://rs.alarmnet.com:443/TotalConnectComfort/WebAPI/emea/api/v1/%s/%s/schedule' % (self.zone_type, self.zoneId), data=zone_info, headers=headers)
        return self._convert(r.text)


class Zone(ZoneBase):

    def __init__(self, client, location, data=None):
        super(Zone, self).__init__()
        self.client = client
        self.location = location
        self.zone_type = 'temperatureZone'
        if data is not None:
            self.__dict__.update(data)

    def is_overridden(self):
        """
        :return: Whether the current setpoint has been overridden
        """
        # Doesn't apply time offset for now
        utcOffset = self.location.__dict__['timeZone']['currentOffsetMinutes']
        timestamp = datetime.utcnow()
        day = timestamp.weekday()
        time = datetime.strptime(timestamp.strftime("%H:%M:%S"), "%H:%M:%S")
        last_setpoint_time = datetime.strptime("00:00:00", "%H:%M:%S")
        last_setpoint_temp = 0.0
        setpoint_temp = self.__dict__["heatSetpointStatus"]["targetTemperature"]
        for setpoint in self.schedule()["DailySchedules"][day]["Switchpoints"]:
            setpoint_time = datetime.strptime(setpoint["TimeOfDay"], "%H:%M:%S")
            if time > last_setpoint_time and time < setpoint_time:
                last_setpoint_temp = setpoint["TargetTemperature"]
                break
            elif time > setpoint_time:
                last_setpoint_temp = setpoint["TargetTemperature"]
                break
            else:
                last_setpoint_time = setpoint_time
        return setpoint_temp == last_setpoint_temp


    def set_temperature(self, temperature, until=None):
        if until is None:
            data = {"HeatSetpointValue":temperature,"SetpointMode":1,"TimeUntil":None}
        else:
            data = {"HeatSetpointValue":temperature,"SetpointMode":2,"TimeUntil":until.strftime('%Y-%m-%dT%H:%M:%SZ')}
        self.client._set_heat_setpoint(data)

    def _set_heat_setpoint(self, data):
        url = 'https://rs.alarmnet.com//TotalConnectComfort/WebAPI/emea/api/v1/temperatureZone/%s/heatSetpoint' % self.zoneId
        headers = dict(self.client.headers)
        headers['Content-Type'] = 'application/json'
        response = requests.put(url, json.dumps(data), headers=headers)

    def cancel_temp_override(self, zone):
        data = {"HeatSetpointValue":0.0,"SetpointMode":0,"TimeUntil":None}
        self._set_heat_setpoint(data)

