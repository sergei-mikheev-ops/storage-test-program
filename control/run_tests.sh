#!/bin/bash

# === Вспомогательная функция: запрос с дефолтом ===
ask_with_default() {
    local prompt="$1"
    local default="$2"
    read -p "$prompt (Enter → $default): " value
    echo "${value:-$default}"
}

# === Настройки ===
USER="testuser"
REMOTE_DIR="/home/$USER"
LOCAL_SCRIPT="../scripts/test_fio_7.py"

# === Проверка скрипта ===
if [ ! -f "$LOCAL_SCRIPT" ]; then
    echo "❌ Ошибка: не найден $LOCAL_SCRIPT"
    exit 1
fi

# === Основной цикл ===
while true; do
    # === 1. Запрос типа хранилища ===
    echo
    echo "=== Выберите тип хранилища ==="
    echo "  1) Локальное (RAID10 на Dell R750)"
    echo "  2) Сетевое iSCSI"
    read -p "Ваш выбор (1/2): " storage_type_num
    case $storage_type_num in
        1) STORAGE_TYPE="local" ;;
        2) STORAGE_TYPE="iscsi" ;;
        *) echo "❌ Неверный выбор. Используется локальное хранилище."; STORAGE_TYPE="local" ;;
    esac

    # === 2. Запрос количества ВМ и IP ===
    read -p "Сколько ВМ будут участвовать в тесте? (например, 1, 2, 4): " VM_COUNT
    if ! [[ "$VM_COUNT" =~ ^[1-9][0-9]*$ ]]; then
        echo "❌ Ошибка: введите целое число ≥ 1"
        exit 1
    fi
    
    declare -a VMS
    for ((i=1; i<=VM_COUNT; i++)); do
        read -p "Введите IP-адрес ВМ #$i: " ip
        if [[ ! $ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            echo "❌ Некорректный IP: $ip"
            exit 1
        fi
        VMS+=("$ip")
    done
    
    # === 3. Количество итераций ===
    ITERATIONS=$(ask_with_default "Количество итераций тестов" "3")
    if ! [[ "$ITERATIONS" =~ ^[1-9][0-9]*$ ]]; then
        echo "❌ Ошибка: введите целое число ≥ 1"
        exit 1
    fi
    
    # === 4. Выбор типа теста ===
    echo
    echo "Выберите тип теста:"
    echo "  1) Только fio"
    echo "  2) Только pgbench"
    echo "  3) fio + pgbench (рекомендуется)"
    read -p "Ваш выбор (1/2/3): " TEST_MODE
    case $TEST_MODE in
        1) RUN_FIO=true;   RUN_PG=false;  ;;
        2) RUN_FIO=false;  RUN_PG=true;   ;;
        3) RUN_FIO=true;   RUN_PG=true;   ;;
        *) echo "❌ Неверный выбор. Используется fio + pgbench."; RUN_FIO=true; RUN_PG=true ;;
    esac
    
    # === 5. Параметры fio (если нужен) ===
    if [ "$RUN_FIO" = true ]; then
        echo
        echo "=== Настройка fio (оставьте пустым для значений по умолчанию) ==="
        TEST_NAME=$(ask_with_default "Название теста" "${STORAGE_TYPE}_${VM_COUNT}vms")
        SIZE=$(ask_with_default "Размер файла" "10G")
        BS=$(ask_with_default "Размер блока" "4k")
        MIX=$(ask_with_default "Процент записи в RW" "60")
        IO_DEPTH=$(ask_with_default "Глубина очереди" "64")
        RUNTIME=$(ask_with_default "Время выполнения (сек)" "60")
    fi
    
    # === 6. Подтверждение ===
    echo
    echo "=== Подтверждение конфигурации ==="
    echo "• Тип хранилища: $STORAGE_TYPE"
    echo "• Количество ВМ: $VM_COUNT"
    echo "• IP-адреса: ${VMS[*]}"
    echo "• Количество итераций: $ITERATIONS"
    echo "• Тесты: $( [ "$RUN_FIO" = true ] && echo "fio " )$( [ "$RUN_PG" = true ] && echo "pgbench" )"
    if [ "$RUN_FIO" = true ]; then
        echo "• fio: ${SIZE}, блок=${BS}, время=${RUNTIME} сек"
    fi
    echo
    read -p "Подтвердить запуск? (y/N): " confirm
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        echo "Отмена."
        exit 0
    fi
    
    # === 7. Копирование скрипта на ВМ ===
    echo -e "\n📤 Копирование скрипта на ВМ..."
    for ip in "${VMS[@]}"; do
        scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
            "$LOCAL_SCRIPT" "$USER@$ip:$REMOTE_DIR/" >/dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo "⚠️ Не удалось скопировать на $ip"
            exit 1
        fi
        echo "  → Скопировано: $ip"
    done
    
    # === 8. Создание директории для результатов ===
    TIMESTAMP=$(date +%Y%m%d_%H%M)
    RESULTS_DIR="results/${TIMESTAMP}_${STORAGE_TYPE}_${VM_COUNT}vms_${ITERATIONS}iter"
    mkdir -p "$RESULTS_DIR"
    echo "📁 Результаты будут сохранены в: ./$RESULTS_DIR/"
    
    # === 9. Цикл по итерациям ===
    for ((iter=1; iter<=ITERATIONS; iter++)); do
        echo -e "\n$(printf '=%.0s' {1..60})"
        echo "🔄 ИТЕРАЦИЯ $iter из $ITERATIONS для хранилища $STORAGE_TYPE"
        echo "$(printf '=%.0s' {1..60})"
        
        # Очистка результатов на ВМ
        echo -e "\n🧹 Очистка предыдущих результатов на ВМ..."
        for ip in "${VMS[@]}"; do
            ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
                "$USER@$ip" "rm -rf $REMOTE_DIR/results/* $REMOTE_DIR/testfile* 2>/dev/null || true"
            echo "  → Очищено: $ip"
        done
        
        # === 10. Формирование команды ===
        if [ "$RUN_FIO" = true ]; then
            CMD="cd $REMOTE_DIR && python3 ./test_fio_7.py"
            CMD="$CMD --test-name '${TEST_NAME}_iter${iter}'"
            CMD="$CMD --size '$SIZE'"
            CMD="$CMD --bs '$BS'"
            CMD="$CMD --mix '$MIX'"
            CMD="$CMD --io-depth $IO_DEPTH"
            CMD="$CMD --runtime $RUNTIME"
        fi
        
        if [ "$RUN_PG" = true ]; then
            if [ "$RUN_FIO" = true ]; then
                CMD="$CMD --run-pgbench"
            else
                CMD="mkdir -p $REMOTE_DIR/results && cd $REMOTE_DIR && sudo -u postgres pgbench -i -s100 postgres"
                CMD="$CMD && sudo -u postgres pgbench -c32 -j4 -T600 -P30 postgres > results/pgbench_iter${iter}_output.txt 2>&1"
            fi
        fi
        
        # === 11. Запуск с прогресс-баром ===
        echo -e "\n🚀 Запуск тестов на ${#VMS[@]} ВМ (итерация $iter)..."
        PIDS=()
        for ip in "${VMS[@]}"; do
            echo "  → Запуск на $ip"
            ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
                "$USER@$ip" "$CMD" > "${RESULTS_DIR}/iter${iter}_log_$ip.log" 2>&1 &
            PIDS+=($!)
            echo "  → Запущено: $ip"
        done
        
        # Прогресс-бар
        echo -n "Прогресс: "
        while kill -0 ${PIDS[0]} 2>/dev/null; do
            echo -n "."
            sleep 10
        done
        wait
        echo " ✅ Завершено."

        # === 12. Сбор результатов ===
        echo -e "\n⬇️ Сбор результатов итерации $iter..."
        for ip in "${VMS[@]}"; do
            echo "  ← $ip"
            
            # ✅ СОЗДАЕМ ЦЕЛЕВУЮ ДИРЕКТОРИЮ ПЕРЕД КОПИРОВАНИЕМ
            mkdir -p "$RESULTS_DIR/iter${iter}_results_$ip"
            
            if [ "$RUN_FIO" = true ] || [ "$RUN_PG" = true ]; then
                # ✅ ДОБАВЛЯЕМ ПРОВЕРКУ НАЛИЧИЯ ИСТОЧНИКА
                if ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
                    "$USER@$ip" "[ -d $REMOTE_DIR/results ] && [ -n \"\$(ls -A $REMOTE_DIR/results 2>/dev/null)\" ]"; then
                    
                    scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -r \
                        "$USER@$ip:$REMOTE_DIR/results/" "$RESULTS_DIR/iter${iter}_results_$ip/" 2>&1 | tee -a "$RESULTS_DIR/iter${iter}_scp_$ip.log"
                    
                    if [ $? -eq 0 ]; then
                        echo "  ✓ Успешно скопировано с $ip"
                    else
                        echo "  ❌ Ошибка копирования с $ip (код: $?)" 
                        echo "    Детали в логе: $RESULTS_DIR/iter${iter}_scp_$ip.log"
                    fi
                else
                    echo "  ❌ Результаты отсутствуют на $ip"
                    ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
                        "$USER@$ip" "ls -la $REMOTE_DIR; ls -la $REMOTE_DIR/results 2>&1 || echo 'Директория results не существует'"
                fi
            fi
        done
        
        # Пауза между итерациями
        if [ $iter -lt $ITERATIONS ]; then
            echo -e "\n⏸️  Пауза 30 секунд перед следующей итерацией..."
            sleep 30
        fi
    done
    
    # === 13. Запрос о тестировании на другом хранилище ===
    echo -e "\n$(printf '=%.0s' {1..60})"
    read -p "Будете тестировать на другом типе хранилища? (y/N): " next_storage
    if [[ ! $next_storage =~ ^[Yy]$ ]]; then
        echo -e "$(printf '=%.0s' {1..60})"
        echo "✅ Все тесты завершены!"
        echo "📊 Для агрегации результатов выполните:"
        echo "   python3 aggregate_results.py results/*/"
        echo "📊 Для визуализации выполните:"
        echo "   python3 visualize_results.py results/*/aggregated_report.json"
        echo "$(printf '=%.0s' {1..60})"
        exit 0
    fi
    
    # === 14. Информация о миграции ===
    echo -e "\n$(printf '=%.0s' {1..60})"
    echo "⚠️  ВАЖНО: Перед продолжением выполните Storage vMotion всех ВМ на другое хранилище."
    echo "   Типы хранилищ в текущем тесте:"
    echo "   - Текущее: $STORAGE_TYPE"
    echo "   - Следующее: $([ "$STORAGE_TYPE" = "local" ] && echo "iscsi" || echo "local")"
    echo "$(printf '=%.0s' {1..60})"
    read -p "Подтвердите, что ВМ перемещены и готовы к тестированию (y/N): " migration_confirm
    if [[ ! $migration_confirm =~ ^[Yy]$ ]]; then
        echo "Тестирование прервано."
        exit 0
    fi
done