#!/usr/bin/env bash
# attack-gateway — управление ботом из терминала
# Использование: ./gateway.sh <команда>

DIR="$(cd "$(dirname "$0")" && pwd)"
PID_DIR="$DIR/.pids"
mkdir -p "$PID_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

save_pid() { echo "$2" > "$PID_DIR/$1.pid"; }
get_pid() { cat "$PID_DIR/$1.pid" 2>/dev/null; }
is_running() { pid=$(get_pid "$1"); [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; }

start_one() {
    local name="$1" log="$2"
    shift 2
    if is_running "$name"; then
        echo -e "  ${YELLOW}●${NC} $name — уже запущен (PID $(get_pid $name))"
        return
    fi
    cd "$DIR"
    if [ -z "$log" ] || [ "$log" = "-" ]; then
        nohup "$@" > /dev/null 2>&1 &
    else
        nohup "$@" >> "$DIR/$log" 2>&1 &
    fi
    local pid=$!
    save_pid "$name" "$pid"
    sleep 0.5
    if kill -0 "$pid" 2>/dev/null; then
        echo -e "  ${GREEN}●${NC} $name — запущен (PID $pid)"
    else
        echo -e "  ${RED}●${NC} $name — ОШИБКА запуска"
    fi
}

stop_one() {
    local name="$1"
    local pid=$(get_pid "$name")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null
        sleep 0.5
        kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null
        echo -e "  ${RED}●${NC} $name — остановлен (PID $pid)"
    else
        echo -e "  ${YELLOW}●${NC} $name — уже не работает"
    fi
    rm -f "$PID_DIR/$name.pid"
}

status_one() {
    local name="$1"
    local pid=$(get_pid "$name")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo -e "  ${GREEN}●${NC} $name — ${GREEN}работает${NC} (PID $pid)"
    else
        echo -e "  ${RED}●${NC} $name — ${RED}остановлен${NC}"
        rm -f "$PID_DIR/$name.pid"
    fi
}

CMD="$1"
shift 2>/dev/null

case "$CMD" in
    start)
        echo -e "${CYAN}🔥 Запуск attack bot...${NC}"
        cd "$DIR"
        start_one "bot" "-" python attack_bot.py
        start_one "watch-slay" "watcher_slay_awards.out.log" bash -c "HERMES_CHANNEL=slay_awards python -u attack_watch.py"
        start_one "watch-stream" "watcher_streaminside.out.log" bash -c "HERMES_CHANNEL=streaminside python -u attack_watch.py"
        start_one "watch-botovod" "watcher_BotovodX.out.log" bash -c "HERMES_CHANNEL=BotovodX python -u attack_watch.py"
        start_one "timer" "-" python timer_notify.py
        echo ""
        echo -e "${GREEN}✅ Все компоненты запущены${NC}"
        ;;

    stop)
        echo -e "${CYAN}🛑 Остановка attack bot...${NC}"
        stop_one "bot"
        stop_one "watch-slay"
        stop_one "watch-stream"
        stop_one "watch-botovod"
        stop_one "timer"
        # Убиваем сирот если остались
        pkill -f "python attack_bot.py" 2>/dev/null
        pkill -f "python -u attack_watch.py" 2>/dev/null
        pkill -f "python timer_notify.py" 2>/dev/null
        sleep 1
        echo ""
        echo -e "${RED}✅ Все компоненты остановлены${NC}"
        ;;

    restart)
        $0 stop
        sleep 1
        $0 start
        ;;

    status)
        echo -e "${CYAN}📊 Статус attack bot:${NC}"
        status_one "bot"
        status_one "watch-slay"
        status_one "watch-stream"
        status_one "watch-botovod"
        status_one "timer"
        ;;

    logs)
        echo -e "${CYAN}📜 Логи (последние 30 строк):${NC}"
        for f in bot.log watcher_slay_awards.log timer_notify.log; do
            if [ -f "$DIR/$f" ]; then
                echo -e "\n${YELLOW}=== $f ===${NC}"
                tail -5 "$DIR/$f"
            fi
        done
        ;;

    *)
        echo -e "${CYAN}attack-gateway — управление attack bot${NC}"
        echo ""
        echo "Команды:"
        echo -e "  ${GREEN}start${NC}    — запустить бота + 3 watcher'а + таймер"
        echo -e "  ${RED}stop${NC}     — остановить всё"
        echo -e "  ${YELLOW}restart${NC}  — перезапустить всё"
        echo -e "  ${CYAN}status${NC}    — статус всех процессов"
        echo -e "  ${CYAN}logs${NC}      — последние логи"
        ;;
esac
