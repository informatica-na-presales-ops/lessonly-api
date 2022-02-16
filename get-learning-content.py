import apscheduler.schedulers.blocking
import lessonly
import notch
import os
import psycopg2.extras
import signal
import sys

log = notch.make_log('lessonly_api.get_learning_content')


def get_database():
    dsn = os.getenv('DB')
    cnx = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.DictCursor)
    return cnx


def upsert_path_steps(cnx, path_steps: list[dict]):
    sql = '''
        insert into lessonly_path_steps (
            archived_at, archived_by_user_id, base_path_id, path_id, resource_id, resource_type,
            step_number
        ) values (
            %(archived_at)s, %(archived_by_user_id)s, %(base_path_id)s, %(path_id)s, %(resource_id)s, %(resource_type)s,
            %(step_number)s
        ) on conflict (base_path_id, path_id, step_number) do update set
            archived_at = %(archived_at)s, archived_by_user_id = %(archived_by_user_id)s, resource_id = %(resource_id)s,
            resource_type = %(resource_type)s
    '''
    with cnx.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, path_steps)


def get_path_steps(base_path_id: int, path_id: int, contents: list[dict], reverse=False):
    if reverse:
        contents = reversed(contents)
    for step_number, step_data in enumerate(contents, start=1):
        yield {
            'archived_at': step_data.get('archived_at'),
            'archived_by_user_id': step_data.get('archived_by_user_id'),
            'base_path_id': base_path_id,
            'path_id': path_id,
            'resource_id': step_data.get('id'),
            'resource_type': step_data.get('resource_type'),
            'step_number': step_number,
        }
        if step_data.get('resource_type') == 'path':
            yield from get_path_steps(base_path_id, step_data.get('id'), step_data.get('contents'))


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
    path_count = 0
    for path in lc.paths:
        path_count += 1
        path_id = path.get('id')
        path_title = path.get('title')
        path_data = lc.get_path(path_id)
        path_step_count = len(path_data.get('contents'))
        log.debug(f'Found a path: {path_id} / {path_title} / {path_step_count} steps')
        path_steps = list(get_path_steps(path_id, path_id, path_data.get('contents'), reverse=True))
        upsert_path_steps(cnx, path_steps)
    log.info(f'Found {path_count} paths')

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
