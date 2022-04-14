import apscheduler.schedulers.blocking
import lessonly
import notch
import os
import psycopg2.extras
import signal
import sys

log = notch.make_log('lessonly_api.get_user_data')


def upsert_users(cur, user_records):
    log.info(f'Found {len(user_records)} user records')
    cur.execute('update lessonly_users_raw set synced = false where synced is true')
    sql = '''
        insert into lessonly_users_raw (
            archived_at, archived_by_user_id, business_unit, department, email, hire_date,
            id, job_title, locale, location, manager_name, mobile_phone_number, name,
            resource_type, role, role_id, synced
        ) values (
            %(archived_at)s, %(archived_by_user_id)s, %(business_unit)s, %(department)s, %(email)s, %(hire_date)s,
            %(id)s, %(job_title)s, %(locale)s, %(location)s, %(manager_name)s, %(mobile_phone_number)s, %(name)s,
            %(resource_type)s, %(role)s, %(role_id)s, true
        ) on conflict (id) do update set
            archived_at = %(archived_at)s, archived_by_user_id = %(archived_by_user_id)s,
            business_unit = %(business_unit)s, department = %(department)s, email = %(email)s,
            hire_date = %(hire_date)s, job_title = %(job_title)s, locale = %(locale)s, location = %(location)s,
            manager_name = %(manager_name)s, mobile_phone_number = %(mobile_phone_number)s, name = %(name)s,
            resource_type = %(resource_type)s, role = %(role)s, role_id = %(role_id)s, synced = true
    '''
    psycopg2.extras.execute_batch(cur, sql, user_records)
    cur.execute('delete from lessonly_users_raw where synced is false')


def upsert_user_custom_fields(cur, cf_records):
    log.info(f'Found {len(cf_records)} user custom field records')
    cur.execute('update lessonly_users_custom_fields_raw set synced = false where synced is true')
    sql = '''
        insert into lessonly_users_custom_fields_raw (
            custom_user_field_id, id, name, synced, user_id, value
        ) values (
            %(custom_user_field_id)s, %(id)s, %(name)s, true, %(user_id)s, %(value)s
        )  on conflict (id) do update set
            custom_user_field_id = %(custom_user_field_id)s, name = %(name)s, synced = true, user_id = %(user_id)s,
            value = %(value)s
    '''
    psycopg2.extras.execute_batch(cur, sql, cf_records)
    cur.execute('delete from lessonly_users_custom_fields_raw where synced is false')


def upsert_user_group_membership(cur, gm_records):
    log.info(f'Found {len(gm_records)} user group membership records')
    cur.execute('update lessonly_user_group_membership_raw set synced = false where synced is true')
    sql = '''
        insert into lessonly_user_group_membership_raw (
            group_id, group_name, synced, user_id
        ) values (
            %(group_id)s, %(group_name)s, true, %(user_id)s
        ) on conflict (user_id, group_id) do update set
            synced = true, group_name = %(group_name)s
    '''
    psycopg2.extras.execute_batch(cur, sql, gm_records)
    cur.execute('delete from lessonly_user_group_membership_raw where synced is false')


def main_job():
    log.info('Running the main job')
    lessonly_api_username = os.getenv('LESSONLY_API_USERNAME')
    if lessonly_api_username is None:
        log.error('You must set the LESSONLY_API_USERNAME environment variable')
        return
    lessonly_api_password = os.getenv('LESSONLY_API_PASSWORD')
    if lessonly_api_password is None:
        log.error('You must set the LESSONLY_API_PASSWORD environment variable')
        return

    cnx = psycopg2.connect(os.getenv('DB'), cursor_factory=psycopg2.extras.DictCursor)

    user_records = []
    cf_records = []
    gm_records = []
    lc = lessonly.LessonlyClient(lessonly_api_username, lessonly_api_password)
    for user in lc.users:
        user_records.append({
            'archived_at': user.get('archived_at'),
            'archived_by_user_id': user.get('archived_by_user_id'),
            'business_unit': user.get('business_unit'),
            'department': user.get('department'),
            'email': user.get('email'),
            'hire_date': user.get('hire_date'),
            'id': user.get('id'),
            'job_title': user.get('job_title'),
            'locale': user.get('locale'),
            'location': user.get('location'),
            'manager_name': user.get('manager_name'),
            'mobile_phone_number': user.get('mobile_phone_number'),
            'name': user.get('name'),
            'resource_type': user.get('resource_type'),
            'role': user.get('role'),
            'role_id': user.get('role_id'),
        })
        for cf in user.get('custom_user_field_data'):
            cf_records.append({
                'custom_user_field_id': cf.get('custom_user_field_id'),
                'id': cf.get('id'),
                'name': cf.get('name'),
                'user_id': user.get('id'),
                'value': cf.get('value'),
            })
        for gm in user.get('groups').get('member'):
            gm_records.append({
                'group_id': gm.get('id'),
                'group_name': gm.get('name'),
                'user_id': user.get('id'),
            })
    with cnx:
        with cnx.cursor() as cur:
            upsert_users(cur, user_records)
            upsert_user_custom_fields(cur, cf_records)
            upsert_user_group_membership(cur, gm_records)
    cnx.close()


def main():
    repeat = os.getenv('REPEAT', 'false').lower() in ('1', 'on', 'true', 'yes')
    if repeat:
        repeat_interval_minutes = int(os.getenv('REPEAT_INTERVAL_MINUTES', '60'))
        log.info(f'This job will repeat every {repeat_interval_minutes} minutes')
        log.info('Change this value by setting the REPEAT_INTERVAL_MINUTES environment variable')
        scheduler = apscheduler.schedulers.blocking.BlockingScheduler()
        scheduler.add_job(main_job, 'interval', minutes=repeat_interval_minutes)
        scheduler.add_job(main_job)
        scheduler.start()
    else:
        main_job()


def handle_sigterm(_signal, _frame):
    sys.exit()


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, handle_sigterm)
    main()
