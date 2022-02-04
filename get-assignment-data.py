import apscheduler.schedulers.blocking
import datetime
import lessonly
import notch
import os
import psycopg2.extras
import signal
import sys

log = notch.make_log('lessonly_api.get_assignment_data')


def get_database():
    dsn = os.getenv('DB')
    cnx = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.DictCursor)
    return cnx


def upsert_assignment(cnx, assignment: dict):
    sql = '''
        insert into lessonly_assignments_raw (
            assignable_id, assignable_type, assigned_at, assignee_id, completed_at, due_by,
            ext_uid, id, is_certification, reassigned_at, resource_type, score, started_at,
            status, updated_at
        ) values (
            %(assignable_id)s, %(assignable_type)s, %(assigned_at)s, %(assignee_id)s, %(completed_at)s, %(due_by)s,
            %(ext_uid)s, %(id)s, %(is_certification)s, %(reassigned_at)s, %(resource_type)s, %(score)s, %(started_at)s,
            %(status)s, %(updated_at)s
        ) on conflict (id) do update set
            assignable_id = %(assignable_id)s, assignable_type = %(assignable_type)s,
            assigned_at = %(assigned_at)s, assignee_id = %(assignee_id)s, completed_at = %(completed_at)s,
            due_by = %(due_by)s, ext_uid = %(ext_uid)s, is_certification = %(is_certification)s,
            reassigned_at = %(reassigned_at)s, resource_type = %(resource_type)s, score = %(score)s,
            started_at = %(started_at)s, status = %(status)s, updated_at = %(updated_at)s
    '''
    if 'is_certification' not in assignment:
        assignment.update({
            'is_certification': None
        })
    with cnx.cursor() as cur:
        cur.execute(sql, assignment)


def upsert_assignment_contents(cnx, contents: list[dict]):
    sql = '''
        insert into lessonly_assignment_contents_raw (
            assignment_id, completed_at, parent, resource_id, resource_type, score,
            started_at, status
        ) values (
            %(assignment_id)s, %(completed_at)s, %(parent)s, %(resource_id)s, %(resource_type)s, %(score)s,
            %(started_at)s, %(status)s
        ) on conflict (assignment_id, resource_id) do update set
            completed_at = %(completed_at)s, parent = %(parent)s, score = %(score)s, started_at = %(started_at)s,
            status = %(status)s
    '''
    with cnx.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, contents)


def get_assignment_contents(cnx, assignment_id: int, parent: int, contents: list[dict]):
    for item in contents:
        item_id = item.get('id')
        log.debug(f'Working on assignment {assignment_id} content item {item_id}')
        if item.get('resource_type') == 'path':
            yield from get_assignment_contents(cnx, assignment_id, item.get('id'), item.get('contents'))
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

    cnx = get_database()

    lc = lessonly.LessonlyClient(lessonly_api_username, lessonly_api_password)
    lc.assignments_updated_at_filter = datetime.date.today()
    log.info(f'Getting assignment data updated on or after {lc.assignments_updated_at_filter}')
    for assignment in lc.assignments:
        a_id = assignment.get('id')
        log.debug(f'Found an assignment: {a_id}')
        upsert_assignment(cnx, assignment)
        if 'contents' in assignment:
            parent = assignment.get('assignable_id')
            contents = list(get_assignment_contents(cnx, a_id, parent, assignment.get('contents')))
            upsert_assignment_contents(cnx, contents)

    cnx.commit()
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
