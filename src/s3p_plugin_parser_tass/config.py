import datetime

from s3p_sdk.plugin.config import (
    PluginConfig,
    CoreConfig,
    TaskConfig,
    trigger,
    MiddlewareConfig,
    modules,
    payload, RestrictionsConfig
)
from s3p_sdk.plugin.types import SOURCE
from s3p_sdk.module import (
    WebDriver,
)

config = PluginConfig(
    plugin=CoreConfig(
        reference='tass',  # уникальное имя источника
        type=SOURCE,  # Тип источника (SOURCE, ML, PIPELINE)
        files=[
            'tass.py',
        ],  # Список файлов, которые будут использоваться в плагине (эти файлы будут сохраняться в платформе)
        is_localstorage=False,
        restrictions=RestrictionsConfig(
            maximum_materials=50,
            to_last_material=None,
            from_date=None,
            to_date=None,
        )
    ),
    task=TaskConfig(
        trigger=trigger.TriggerConfig(
            type=trigger.SCHEDULE,
            interval=datetime.timedelta(days=1),  # Интервал перезапуска плагина
        )
    ),
    middleware=MiddlewareConfig(
        modules=[
            modules.TimezoneSafeControlConfig(order=1, is_critical=True),
            modules.SaveOnlyNewDocuments(order=2, is_critical=True),
        ],
        bus=None,
    ),
    payload=payload.PayloadConfig(
        file='tass.py',  # python файл плагина (точка входа). Этот файл должен быть указан в `plugin.files[*]`
        classname='TASS',  # имя python класса в указанном файле
        entry=payload.entry.EntryConfig(
            method='content',
            params=[
                payload.entry.ConstParamConfig('feeds', [
                    'https://tass.ru/rss/v2.xml'
                ])

            ]  # Подробнее можно почитать [тут](./readme.md#пример-конфигурации-параметров-запуска-плагина
        )
    )
)

__all__ = ['config']
