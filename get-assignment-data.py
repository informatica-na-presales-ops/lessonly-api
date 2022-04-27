import apscheduler.schedulers.blocking
import lessonly
import notch
import os
import psycopg2.extras
import signal
import sys

log = notch.make_log('lessonly_api.get_assignment_data')


def upsert_assignment(cnx, records: list[dict]):
    log.info(f'Sending {len(records)} assignment records to postgres')
    sql = '''
        insert into lessonly_assignments_raw (
            assignable_id, assignable_type, assigned_at, assignee_id, completed_at, due_by,
            ext_uid, id, is_certification, reassigned_at, resource_type, score, started_at,
            status, updated_at, _synced
        ) values (
            %(assignable_id)s, %(assignable_type)s, %(assigned_at)s, %(assignee_id)s, %(completed_at)s, %(due_by)s,
            %(ext_uid)s, %(id)s, %(is_certification)s, %(reassigned_at)s, %(resource_type)s, %(score)s, %(started_at)s,
            %(status)s, %(updated_at)s, true
        ) on conflict (id) do update set
            assignable_id = %(assignable_id)s, assignable_type = %(assignable_type)s,
            assigned_at = %(assigned_at)s, assignee_id = %(assignee_id)s, completed_at = %(completed_at)s,
            due_by = %(due_by)s, ext_uid = %(ext_uid)s, is_certification = %(is_certification)s,
            reassigned_at = %(reassigned_at)s, resource_type = %(resource_type)s, score = %(score)s,
            started_at = %(started_at)s, status = %(status)s, updated_at = %(updated_at)s, _synced = true
    '''
    with cnx:
        with cnx.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, records)


def upsert_assignment_contents(cnx, records: list[dict]):
    log.info(f'Sending {len(records)} assignment content records to postgres')
    sql = '''
        insert into lessonly_assignment_contents_raw (
            assignment_id, completed_at, parent, resource_id, resource_type, score,
            started_at, status, _synced
        ) values (
            %(assignment_id)s, %(completed_at)s, %(parent)s, %(resource_id)s, %(resource_type)s, %(score)s,
            %(started_at)s, %(status)s, true
        ) on conflict (assignment_id, resource_id) do update set
            completed_at = %(completed_at)s, parent = %(parent)s, score = %(score)s, started_at = %(started_at)s,
            status = %(status)s, _synced = true
    '''
    with cnx:
        with cnx.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, records)


def get_assignment_contents(assignment_id: int, parent: int, contents: list[dict]):
    for item in contents:
        item_id = item.get('id')
        log.debug(f'Working on assignment {assignment_id} content item {item_id}')
        if item.get('resource_type') == 'path':
            yield from get_assignment_contents(assignment_id, item.get('id'), item.get('contents'))
        else:
            params = {
                'assignment_id': assignment_id,
                'completed_at': item.get('completed_at'),
                'parent': parent,
                'resource_id': item.get('id'),
                'resource_type': item.get('resource_type'),
                'score': item.get('score'),
                'started_at': item.get('started_at'),
                'status': item.get('status'),
            }
            yield params


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

    # turn off the _synced flag for all records
    with cnx:
        with cnx.cursor() as cur:
            cur.execute('''
                update lessonly_assignments_raw
                set _synced = false where _synced is true or _synced is null
            ''')
            cur.execute('''
                update lessonly_assignment_contents_raw
                set _synced = false where _synced is true or _synced is null
            ''')

    lc = lessonly.LessonlyClient(lessonly_api_username, lessonly_api_password)

    assignment_records = []
    content_records = []

    for assignment in lc.assignments:
        a_id = assignment.get('id')
        log.debug(f'Found an assignment: {a_id}')
        assignment.setdefault('is_certification', None)
        assignment_records.append(assignment)
        if 'contents' in assignment:
            parent = assignment.get('assignable_id')
            content_records.extend(get_assignment_contents(a_id, parent, assignment.get('contents')))

        # send records to postgres when we have collected enough
        if len(assignment_records) > 999:
            upsert_assignment(cnx, assignment_records)
            assignment_records = []
        if len(content_records) > 999:
            upsert_assignment_contents(cnx, content_records)
            content_records = []

    # send leftover records
    if assignment_records:
        upsert_assignment(cnx, assignment_records)
    if content_records:
        upsert_assignment_contents(cnx, content_records)

    # remove records that were not included in this sync
    with cnx:
        with cnx.cursor() as cur:
            cur.execute('''
                delete from lessonly_assignments_raw where _synced is false
            ''')
            cur.execute('''
                delete from lessonly_assignment_contents_raw where _synced is false
            ''')

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
