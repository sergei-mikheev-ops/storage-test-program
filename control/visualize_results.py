#!/usr/bin/env python3
"""
Исправленный скрипт для визуализации результатов тестирования.
Создает наглядные графики для сравнения результатов между разными конфигурациями.
"""
import json
import sys
import os
import re
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
matplotlib.use('Agg')  # Для работы без GUI

# Цветовая схема для типов хранилищ
STORAGE_COLORS = {
    'local': '#1f77b4',  # Синий для локального хранилища
    'iscsi': '#ff7f0e',  # Оранжевый для iSCSI
    'default': '#2ca02c'  # Зеленый для неопознанных типов
}

def get_storage_type(label):
    """Извлекает тип хранилища из метки"""
    label_lower = label.lower()
    if 'local' in label_lower:
        return 'local'
    elif 'iscsi' in label_lower:
        return 'iscsi'
    else:
        return 'default'

def get_color_for_storage(storage_type):
    """Возвращает цвет для типа хранилища"""
    return STORAGE_COLORS.get(storage_type, STORAGE_COLORS['default'])

def load_aggregated_data(json_file):
    """Загружает агрегированные данные из JSON с обработкой ошибок"""
    try:
        with open(json_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Ошибка загрузки {json_file}: {str(e)}")
        return None

def validate_data_for_visualization(datasets):
    """Проверяет данные на наличие необходимых полей и корректность"""
    valid_datasets = {}
    test_types_found = set()
    
    for label, data in datasets.items():
        if not data or 'fio' not in data:
            print(f"⚠️  Пропущен датасет {label}: отсутствуют данные FIO")
            continue
        
        # Собираем типы тестов
        test_types = list(data['fio'].keys())
        test_types_found.update(test_types)
        
        # Проверяем наличие необходимых полей в каждом тесте
        valid_tests = {}
        for test_name, metrics in data['fio'].items():
            required_fields = ['IOPS_mean', 'Bandwidth_mean', 'Latency_mean']
            if all(field in metrics for field in required_fields):
                valid_tests[test_name] = metrics
            else:
                print(f"⚠️  Пропущен тест '{test_name}' в {label}: отсутствуют необходимые поля")
        
        if not valid_tests:
            print(f"⚠️  Пропущен датасет {label}: нет валидных тестов")
            continue
        
        # Создаем копию данных с только валидными тестами
        valid_data = data.copy()
        valid_data['fio'] = valid_tests
        valid_datasets[label] = valid_data
    
    if not valid_datasets:
        print("❌ Не найдено валидных датасетов для визуализации")
        return None, None
    
    print(f"✅ Найдено {len(valid_datasets)} валидных датасетов")
    print(f"✅ Найдены тесты: {', '.join(sorted(test_types_found))}")
    
    # Определяем стандартный набор тестов для визуализации
    standard_tests = [
        "Sequential Write",
        "Sequential Read",
        "Random Write",
        "Random Read",
        "Mixed RW (Write)",
        "Mixed RW (Read)"
    ]
    
    # Фильтруем только стандартные тесты, которые есть в данных
    filtered_tests = [test for test in standard_tests if test in test_types_found]
    
    if not filtered_tests:
        print("⚠️  Не найдены стандартные тесты для визуализации")
        filtered_tests = sorted(test_types_found)[:6]  # Берем первые 6 тестов
    
    return valid_datasets, filtered_tests

def plot_fio_comparison(datasets, filtered_tests, output_dir):
    """Создает графики сравнения FIO тестов с улучшенной визуализацией"""
    if not filtered_tests or not datasets:
        print("⚠️  Нет данных для визуализации FIO")
        return
    
    # Создаем отдельные графики для каждой метрики
    metrics = ['IOPS', 'Bandwidth', 'Latency']
    metric_titles = {
        'IOPS': 'Сравнение IOPS между конфигурациями',
        'Bandwidth': 'Сравнение пропускной способности между конфигурациями',
        'Latency': 'Сравнение задержек между конфигурациями'
    }
    metric_labels = {
        'IOPS': 'IOPS (тысячи)',
        'Bandwidth': 'Bandwidth (MiB/s)',
        'Latency': 'Latency (ms)'
    }
    
    x = range(len(filtered_tests))
    width = 0.8 / len(datasets)
    
    for metric in metrics:
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Для каждой конфигурации (датасета)
        for idx, (label, data) in enumerate(datasets.items()):
            values = []
            errors = []
            
            for test in filtered_tests:
                if test in data['fio']:
                    values.append(data['fio'][test][f'{metric}_mean'])
                    errors.append(data['fio'][test][f'{metric}_stdev'])
                else:
                    values.append(0)
                    errors.append(0)
            
            # Определяем цвет на основе типа хранилища
            storage_type = get_storage_type(label)
            color = get_color_for_storage(storage_type)
            
            # Вычисляем позицию столбцов
            offset = width * idx - width * (len(datasets) - 1) / 2
            
            # Создаем столбцы
            bars = ax.bar([i + offset for i in x], values, width,
                          yerr=errors, capsize=5, color=color, alpha=0.8,
                          label=f"{storage_type.upper()} ({data['num_vms']} VM)")
            
            # Добавляем значения внутри столбцов
            for i, bar in enumerate(bars):
                height = bar.get_height()
                if height > 0:
                    # Позиция текста зависит от высоты столбца
                    text_y = height * 0.5 if height > 10 else height + (height * 0.05)
                    text_color = 'white' if height > 10 else 'black'
                    fontsize = 8 if len(datasets) > 2 else 9
                    
                    ax.text(bar.get_x() + bar.get_width()/2., text_y,
                           f'{height:.1f}',
                           ha='center', va='center', fontsize=fontsize, color=text_color)
        
        # Настройки графика
        ax.set_xlabel('Тип теста', fontsize=12)
        ax.set_ylabel(metric_labels[metric], fontsize=12)
        ax.set_title(metric_titles[metric], fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels([t.replace(' ', '\n') for t in filtered_tests], rotation=15, ha='center')
        ax.legend(title='Конфигурация', loc='upper right')
        ax.grid(axis='y', alpha=0.3)
        
        # Устанавливаем отступы для заголовка
        plt.subplots_adjust(top=0.85)
        
        # Сохраняем график
        plt.savefig(os.path.join(output_dir, f'fio_{metric.lower()}_comparison.png'), dpi=300, bbox_inches='tight')
        plt.close()
    
    print("✅ Графики FIO созданы")

def plot_pgbench_comparison(datasets, output_dir):
    """Создает графики сравнения pgbench тестов"""
    # Фильтруем датасеты с данными pgbench
    pgbench_data = {label: data for label, data in datasets.items() 
                    if 'pgbench' in data and data['pgbench']}
    
    if not pgbench_data:
        print("⚠️  Нет данных pgbench для визуализации")
        return
    
    # Группируем данные по типам хранилищ
    storage_groups = {}
    for label, data in pgbench_data.items():
        storage_type = get_storage_type(label)
        vm_count = data.get('num_vms', 1)
        key = (storage_type, vm_count)
        
        if key not in storage_groups:
            storage_groups[key] = []
        storage_groups[key].append(data['pgbench'])
    
    if not storage_groups:
        print("⚠️  Нет группируемых данных pgbench")
        return
    
    # Создаем два графика в одной фигуре
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # График TPS
    x = range(len(storage_groups))
    width = 0.6
    
    for idx, ((storage_type, vm_count), pg_data) in enumerate(storage_groups.items()):
        tps_values = [d['TPS_mean'] for d in pg_data]
        tps_errors = [d['TPS_stdev'] for d in pg_data]
        
        avg_tps = mean(tps_values)
        avg_error = mean(tps_errors) if len(tps_errors) > 1 else tps_errors[0]
        
        color = get_color_for_storage(storage_type)
        bar = ax1.bar(idx, avg_tps, width, yerr=avg_error, capsize=10, 
                     color=color, alpha=0.8, label=f"{storage_type.upper()} ({vm_count} VM)")
        
        # Добавляем значение на столбец
        height = bar[0].get_height()
        ax1.text(bar[0].get_x() + bar[0].get_width()/2., height + (height * 0.05),
                f'{height:.0f}',
                ha='center', va='bottom', fontsize=9)
    
    ax1.set_xlabel('Конфигурация', fontsize=12)
    ax1.set_ylabel('TPS (транзакций в секунду)', fontsize=12)
    ax1.set_title('Сравнение TPS (pgbench)', fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels([f"{storage.upper()}\n({vm} VM)" for (storage, vm) in storage_groups.keys()], 
                       rotation=15, ha='center')
    ax1.grid(axis='y', alpha=0.3)
    
    # График задержки
    for idx, ((storage_type, vm_count), pg_data) in enumerate(storage_groups.items()):
        lat_values = [d['Latency_Avg_mean'] for d in pg_data]
        lat_errors = [d['Latency_Avg_stdev'] for d in pg_data]
        
        avg_lat = mean(lat_values)
        avg_error = mean(lat_errors) if len(lat_errors) > 1 else lat_errors[0]
        
        color = get_color_for_storage(storage_type)
        bar = ax2.bar(idx, avg_lat, width, yerr=avg_error, capsize=10,
                     color=color, alpha=0.8, label=f"{storage_type.upper()} ({vm_count} VM)")
        
        # Добавляем значение на столбец
        height = bar[0].get_height()
        ax2.text(bar[0].get_x() + bar[0].get_width()/2., height + (height * 0.05),
                f'{height:.2f}',
                ha='center', va='bottom', fontsize=9)
    
    ax2.set_xlabel('Конфигурация', fontsize=12)
    ax2.set_ylabel('Средняя задержка (ms)', fontsize=12)
    ax2.set_title('Сравнение задержки (pgbench)', fontsize=14, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"{storage.upper()}\n({vm} VM)" for (storage, vm) in storage_groups.keys()],
                       rotation=15, ha='center')
    ax2.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'pgbench_comparison.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    print("✅ Графики pgbench созданы")

def plot_scalability_analysis(datasets, output_dir):
    """Создает график масштабируемости производительности"""
    # Группируем данные по количеству ВМ для каждого типа хранилища
    scalability_data = {}
    
    for label, data in datasets.items():
        storage_type = get_storage_type(label)
        vm_count = data.get('num_vms', 1)
        
        if storage_type not in scalability_data:
            scalability_data[storage_type] = {}
        
        # Собираем базовые метрики для анализа масштабируемости
        if 'Random Read' in data['fio'] and 'Random Write' in data['fio']:
            scalability_data[storage_type][vm_count] = {
                'read_iops': data['fio']['Random Read']['IOPS_mean'],
                'write_iops': data['fio']['Random Write']['IOPS_mean']
            }
    
    if len(scalability_data) < 2 or any(len(vm_data) < 2 for vm_data in scalability_data.values()):
        print("⚠️  Недостаточно данных для анализа масштабируемости")
        return
    
    # Создаем графики масштабируемости
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # График масштабируемости чтения
    x_positions = range(len(next(iter(scalability_data.values()))))
    bar_width = 0.8 / len(scalability_data)
    
    for idx, (storage_type, vm_data) in enumerate(scalability_data.items()):
        vm_counts = sorted(vm_data.keys())
        read_iops = [vm_data[vm]['read_iops'] for vm in vm_counts]
        color = get_color_for_storage(storage_type)
        
        offset = bar_width * idx - bar_width * (len(scalability_data) - 1) / 2
        bars = ax1.bar([x + offset for x in x_positions], read_iops, bar_width,
                      color=color, alpha=0.8, label=storage_type.upper())
        
        # Добавляем значения на столбцы
        for i, bar in enumerate(bars):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + (height * 0.05),
                    f'{height:.0f}',
                    ha='center', va='bottom', fontsize=9)
    
    ax1.set_xlabel('Количество ВМ', fontsize=12)
    ax1.set_ylabel('Random Read IOPS', fontsize=12)
    ax1.set_title('Масштабируемость: Random Read', fontsize=14, fontweight='bold')
    ax1.set_xticks(x_positions)
    ax1.set_xticklabels(sorted(next(iter(scalability_data.values())).keys()))
    ax1.legend(title='Тип хранилища')
    ax1.grid(axis='y', alpha=0.3)
    
    # График масштабируемости записи
    for idx, (storage_type, vm_data) in enumerate(scalability_data.items()):
        vm_counts = sorted(vm_data.keys())
        write_iops = [vm_data[vm]['write_iops'] for vm in vm_counts]
        color = get_color_for_storage(storage_type)
        
        offset = bar_width * idx - bar_width * (len(scalability_data) - 1) / 2
        bars = ax2.bar([x + offset for x in x_positions], write_iops, bar_width,
                      color=color, alpha=0.8, label=storage_type.upper())
        
        # Добавляем значения на столбцы
        for i, bar in enumerate(bars):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + (height * 0.05),
                    f'{height:.0f}',
                    ha='center', va='bottom', fontsize=9)
    
    ax2.set_xlabel('Количество ВМ', fontsize=12)
    ax2.set_ylabel('Random Write IOPS', fontsize=12)
    ax2.set_title('Масштабируемость: Random Write', fontsize=14, fontweight='bold')
    ax2.set_xticks(x_positions)
    ax2.set_xticklabels(sorted(next(iter(scalability_data.values())).keys()))
    ax2.legend(title='Тип хранилища')
    ax2.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'scalability_analysis.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    print("✅ График масштабируемости создан")

def find_aggregated_reports(input_paths):
    """Находит все файлы с агрегированными данными в указанных путях"""
    report_files = []
    
    for path in input_paths:
        path_obj = Path(path)
        
        # Если это файл
        if path_obj.is_file():
            if path_obj.name == 'aggregated_report.json':
                report_files.append(str(path_obj))
            continue
        
        # Если это директория, ищем в ней и поддиректориях
        if path_obj.is_dir():
            for file in path_obj.rglob('aggregated_report.json'):
                report_files.append(str(file))
            continue
    
    if not report_files:
        print("❌ Не найдено файлов агрегированных данных")
        print(f"🔍 Поиск проводился в: {', '.join(input_paths)}")
        print("🔍 Искались файлы: aggregated_report.json")
        
        # Показываем структуру для диагностики
        print("\n📂 Структура директорий:")
        for path in input_paths:
            path_obj = Path(path)
            if path_obj.is_dir():
                print(f"\n{path}:")
                for item in path_obj.rglob('*'):
                    if item.is_file():
                        print(f"  • {item.relative_to(path_obj)}")
    
    return report_files

def main():
    if len(sys.argv) < 2:
        print("Использование: python3 visualize_results.py <папка1> [<папка2> ...] или <json_файл1> [<json_файл2> ...]")
        print("\nПримеры:")
        print("  python3 visualize_results.py results/*/")
        print("  python3 visualize_results.py results/20251218_1619_local_1vms_2iter/ results/20251218_1722_iscsi_1vms_2iter/")
        print("  python3 visualize_results.py results/*/aggregated_report.json")
        sys.exit(1)
    
    # Находим файлы с агрегированными данными
    report_files = find_aggregated_reports(sys.argv[1:])
    
    if not report_files:
        sys.exit(1)
    
    # Загружаем данные из всех файлов
    datasets = {}
    for json_path in report_files:
        data = load_aggregated_data(json_path)
        if data:
            # Извлекаем метку из пути
            parent_dir = Path(json_path).parent
            label = parent_dir.name
            datasets[label] = data
            print(f"✅ Загружен: {json_path} -> {label}")
    
    if not datasets:
        print("❌ Не удалось загрузить данные для визуализации")
        sys.exit(1)
    
    # Валидация и фильтрация данных
    valid_datasets, filtered_tests = validate_data_for_visualization(datasets)
    
    if not valid_datasets or not filtered_tests:
        print("❌ Нет валидных данных для визуализации")
        sys.exit(1)
    
    # Создаем директорию для графиков
    output_dir = "visualization_output"
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n📊 Создание графиков в: {output_dir}/")
    
    # Создаем графики
    plot_fio_comparison(valid_datasets, filtered_tests, output_dir)
    plot_pgbench_comparison(valid_datasets, output_dir)
    plot_scalability_analysis(valid_datasets, output_dir)
    
    print(f"\n✅ Визуализация завершена!")
    print(f"📁 Графики сохранены в: {output_dir}/")
    print("\nСозданные файлы:")
    for file in sorted(os.listdir(output_dir)):
        if file.endswith('.png'):
            print(f"  • {file}")

if __name__ == "__main__":
    main()