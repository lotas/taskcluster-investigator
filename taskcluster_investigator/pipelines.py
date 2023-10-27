import functools
import logging
from enum import StrEnum
from dataclasses import dataclass

from .cache import read_cache_file, write_cache_file
from .utils import load_pipeline_files
from .taskcluster import lookup_tasks
from .aggregations import summarize, extract_fields
from .gcp import query_logs

logger = logging.getLogger("pipelines")


class QueryType(StrEnum):
    input = "input"
    query = "gcp-query"
    query_multi = "gcp-query-multi"
    lookup_tasks = "taskcluster-lookup-tasks"
    summarize = "summarize"
    count = "count"


query_type_to_func = {
    QueryType.input: lambda q, res, params: q.data,
    QueryType.query: lambda q, res, params: query_logs(q.query, **params),
    QueryType.lookup_tasks: lambda q, res, params: lookup_tasks(res, q.field),
    QueryType.summarize: lambda q, res, params: summarize(res, q.fields),
    QueryType.count: None,
}


@dataclass
class Query:
    type: QueryType
    name: str | None
    description: str | None
    field: str | None
    iterate: dict[str, str] | None
    extract: dict[str, str] | None
    fields: dict[str, str] | None
    query: str | None
    data: dict[str, any] | list[any] | None
    cache: bool = True

    def _use_cache(self):
        return self.type in [QueryType.query, QueryType.lookup_tasks]

    def run(self, results, params=None):
        logger.info("running query: %s [type: %s]", self.name, self.type)

        out = None
        use_cache = self._use_cache()
        if use_cache:
            out = read_cache_file(self.name, [self, results])

        if not use_cache or not out:
            fn = query_type_to_func[self.type]
            if not fn:
                raise Exception(f"Unknown query type: {self.type}")
            out = fn(self, results, params)

        if use_cache:
            write_cache_file(self.name, [self, results], out)

        if self.extract:
            out = extract_fields(out, self.extract)

        return out


@dataclass
class Pipeline:
    id: str  # filename
    name: str
    description: str | None
    queries: list[Query] | None

    params: dict[str, any] | None = None

    def set_params(self, params):
        self.params = params
        return self

    def run(self):
        logger.info("running pipeline: %s [%s]", self.name, self.id)
        results = {}
        # each query will use results as input and return results as output
        # doesn't support multi-channel output yet, more like a pipeline
        for query in self.queries:
            results = query.run(results, params=self.params)
            logger.debug("results: %s", results)
        return results


@functools.lru_cache
def get_pipeline_by_name(name):
    if not name:
        raise Exception("Pipeline name not given")

    found = []
    for pipeline in load_pipelines():
        if name in pipeline.name or name in pipeline.id:
            found.append(pipeline)

    if len(found) == 0:
        raise Exception(f"Pipeline not found: {name}")

    if len(found) > 1:
        names = ", ".join([f"{p.name} ({p.id}.yml)" for p in found])
        raise Exception(f"Several pipelines match given name: {name} [{names}]")

    return found.pop()


def load_pipelines():
    def get_key(obj, key, default=None):
        if key in obj:
            return obj[key]
        return default

    pipelines = []
    for obj in load_pipeline_files():
        pipeline = Pipeline(
            id=obj["id"],
            name=obj["name"],
            description=get_key(obj, "description"),
            queries=[],
        )
        for q in get_key(obj, "queries"):
            pipeline.queries.append(
                Query(
                    name=get_key(q, "name"),
                    type=QueryType(get_key(q, "type")),
                    description=get_key(q, "description"),
                    cache=get_key(q, "cache", True),
                    field=get_key(q, "field"),
                    fields=get_key(q, "fields"),
                    iterate=get_key(q, "iterate"),
                    extract=get_key(q, "extract"),
                    query=get_key(q, "query"),
                    data=get_key(q, "data"),
                )
            )
        pipelines.append(pipeline)
        logger.debug(f"Loaded pipeline: {pipeline.name} ({len(pipeline.queries)})")

    return pipelines
