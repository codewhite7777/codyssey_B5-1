"""CLI: 한 줄 입력 → 나누기(파싱) → 실행 → Redis 스타일로 출력.

    mini-redis> SET user:1 "Alice"
                 │
     parse_line  ▼  ["SET", "user:1", "Alice"]
                 │
     execute     ▼  MiniRedis.set("user:1", "Alice")
                 │
     출력        ▼  OK
"""

from mini_redis.store import MiniRedis, OutOfMemoryError

PROMPT = "mini-redis> "

ERR_UNKNOWN = "(error) ERR unknown command '{}'"
ERR_ARGS = "(error) ERR wrong number of arguments for '{}' command"
ERR_INT = "(error) ERR value is not an integer or out of range"
ERR_OOM = "(error) OOM command not allowed when used_memory > 'maxmemory'"
ERR_QUOTES = "(error) ERR unbalanced quotes in request"
ERR_CONFIG = "(error) ERR unsupported CONFIG parameter: only 'CONFIG SET maxmemory <bytes>' is supported"


class ParseError(Exception):
    """따옴표가 닫히지 않은 입력."""


def parse_line(line):
    """한 줄을 단어(토큰) 리스트로 나눈다.

    - 공백으로 나눈다:            SET user:1 Alice      -> ["SET", "user:1", "Alice"]
    - 큰따옴표 안은 한 덩어리:    SET msg "hello world" -> ["SET", "msg", "hello world"]
    - 따옴표가 안 닫히면 ParseError
    """
    tokens = []
    current = ""
    in_quotes = False
    has_token = False  # "" 처럼 빈 문자열 값도 토큰으로 인정하려고
    for ch in line:
        if in_quotes:
            if ch == '"':
                in_quotes = False
            else:
                current += ch
        elif ch == '"':
            in_quotes = True
            has_token = True
        elif ch.isspace():
            if has_token:
                tokens.append(current)
                current = ""
                has_token = False
        else:
            current += ch
            has_token = True
    if in_quotes:
        raise ParseError()
    if has_token:
        tokens.append(current)
    return tokens


def parse_int(text):
    """정수로 바꾼다. 실패하면 None."""
    try:
        return int(text)
    except ValueError:
        return None


def format_integer(n):
    return "(integer) {}".format(n)


def format_bulk(value):
    return "(nil)" if value is None else '"{}"'.format(value)


def format_array(items):
    if not items:
        return "(empty array)"
    lines = []
    for i, item in enumerate(items, start=1):
        lines.append('{}. "{}"'.format(i, item))
    return "\n".join(lines)


def execute(db, tokens):
    """토큰 리스트를 받아 명령을 실행하고, 출력할 글자를 돌려준다."""
    name = tokens[0].upper()
    args = tokens[1:]
    argc = len(args)

    if name == "SET":
        if argc != 2:
            return ERR_ARGS.format(name)
        try:
            db.set(args[0], args[1])
        except OutOfMemoryError:
            return ERR_OOM
        return "OK"

    if name == "GET":
        if argc != 1:
            return ERR_ARGS.format(name)
        return format_bulk(db.get(args[0]))

    if name == "DEL":
        if argc != 1:
            return ERR_ARGS.format(name)
        return format_integer(db.delete(args[0]))

    if name == "EXISTS":
        if argc != 1:
            return ERR_ARGS.format(name)
        return format_integer(db.exists(args[0]))

    if name == "DBSIZE":
        if argc != 0:
            return ERR_ARGS.format(name)
        return format_integer(db.dbsize())

    if name == "KEYS":
        if argc != 0:
            return ERR_ARGS.format(name)
        return format_array(db.keys())

    if name == "CONFIG":
        if argc != 3:
            return ERR_ARGS.format(name)
        if args[0].upper() != "SET" or args[1].lower() != "maxmemory":
            return ERR_CONFIG
        limit = parse_int(args[2])
        if limit is None or limit < 0:
            return ERR_INT
        db.set_maxmemory(limit)
        return "OK"

    if name == "INFO":
        if argc > 1 or (argc == 1 and args[0].lower() != "memory"):
            return ERR_ARGS.format(name)
        used, limit, evicted = db.info_memory()
        return "used_memory:{}\nmaxmemory:{}\nevicted_keys:{}".format(used, limit, evicted)

    if name == "EXPIRE":
        if argc != 2:
            return ERR_ARGS.format(name)
        seconds = parse_int(args[1])
        if seconds is None:
            return ERR_INT
        return format_integer(db.expire(args[0], seconds))

    if name == "TTL":
        if argc != 1:
            return ERR_ARGS.format(name)
        return format_integer(db.ttl(args[0]))

    return ERR_UNKNOWN.format(tokens[0])


def handle_line(db, line):
    """한 줄 처리. 빈 줄이면 None(출력 없음)."""
    try:
        tokens = parse_line(line)
    except ParseError:
        return ERR_QUOTES
    if not tokens:
        return None
    return execute(db, tokens)


def run():
    """REPL: 프롬프트 출력 → 입력 읽기 → 실행 → 출력을 exit/quit까지 반복."""
    db = MiniRedis()
    while True:
        try:
            line = input(PROMPT)
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.strip().lower() in ("exit", "quit"):
            break
        result = handle_line(db, line)
        if result is not None:
            print(result)
