from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import sys
    sys.path.append(str(Path(__file__).absolute().parent / 'build/release'))
    import cru
    available = True
except ModuleNotFoundError:
    available = False


def get_image_info_dict(path: Path) -> dict[str, Any] | None:
    if not available:
        return None

    try:
        data = cru.load_image_info(str(path))
        if not data:
            return None

        fields = {}

        if data.times.original:
            capture_date = datetime.fromtimestamp(data.times.original.seconds, timezone.utc)
            capture_date = capture_date.astimezone(timezone(timedelta(seconds=data.times.original.offset)))
            fields['captureDateTime'] = capture_date.isoformat()
        if data.times.gps:
            if data.times.gps.date_only:
                fields['gpsDate'] = date.fromtimestamp(data.times.gps.seconds).isoformat()
            else:
                fields['gpsDateTime'] = datetime.fromtimestamp(data.times.gps.seconds, timezone.utc).isoformat()

        if data.make_and_model.camera:
            fields['cameraMakeAndModel'] = data.make_and_model.camera
        if data.make_and_model.lens:
            fields['lensMakeAndModel'] = data.make_and_model.lens

        if data.camera_settings.aperture:
            fields['apertureSetting'] = data.camera_settings.aperture
        if data.camera_settings.exposure:
            fields['exposureSetting'] = data.camera_settings.exposure
        if data.camera_settings.iso:
            fields['isoSetting'] = data.camera_settings.iso
        if data.camera_settings.focal_length:
            fields['focalLengthSetting'] = data.camera_settings.focal_length

        if data.gps.longitude:
            fields['gpsLongitude'] = data.gps.longitude
        if data.gps.latitude:
            fields['gpsLatitude'] = data.gps.latitude
        if data.gps.altitude:
            fields['gpsAltitude'] = data.gps.altitude
        if data.gps.speed:
            fields['gpsSpeed'] = data.gps.speed
        if data.gps.direction:
            fields['gpsDirection'] = data.gps.direction
        fields['gpsZeroDirection'] = data.gps.zero_direction.name

        return fields
    except Exception:
        return None
