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

def add_value_labels(ax, bars, values):
    """Добавляет значения на/внутри столбцов с адаптивным позиционированием"""
    max_height = max(bar.get_height() for bar in bars if bar.get_height() > 0)
    
    for i, (bar, value) in enumerate(zip(bars, values)):
        height = bar.get_height()
        if height == 0:
            continue
            
        # Определяем позицию текста
        if height > max_height * 0.1:  # Достаточно большой столбец
            if height > 10:  # Очень высокий столбец - текст внутри
                text_y = height * 0.5
                va = 'center'
                color = 'white'
                fontsize = max(8, 10 - len(bars))
            else:  # Средний столбец - текст немного выше
                text_y = height + (max_height * 0.05)
                va = 'bottom'
                color = 'black'
                fontsize = 9
        else:  # Маленький столбец - текст сбоку
            text_y = height + (max_height * 0.05)
            va = 'bottom'
            color = 'black'
            fontsize = 8
        
        ax.text(bar.get_x() + bar.get_width()/2., text_y,
               f'{value:.1f}',
               ha='center', va=va, fontsize=fontsize, color=color,
               bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=0.5) if height < max_height * 0.1 else None)

def extract_pgbench_data(data):
    """Извлекает данные pgbench из разных форматов"""
    if 'pgbench' in data and isinstance(data['pgbench'], dict):
        # Стандартный JSON формат
        pg_data = data['pgbench']
        if 'TPS_mean' in pg_data:
            return {
                'TPS_mean': pg_data['TPS_mean'],
                'TPS_stdev': pg_data.get('TPS_stdev', 0),
                'Latency_Avg_mean': pg_data['Latency_Avg_mean'],
                'Latency_Avg_stdev': pg_data.get('Latency_Avg_stdev', 0),
                'samples': pg_data.get('samples', 1)
            }
        elif 'TPS' in pg_data:
            return {
                'TPS_mean': pg_data['TPS'],
                'TPS_stdev': pg_data.get('TPS_stdev', 0),
                'Latency_Avg_mean': pg_data['Latency_Avg'],
                'Latency_Avg_stdev': pg_data.get('Latency_Avg_stdev', 0),
                'samples': pg_data.get('samples', 1)
            }
    
    # Поиск в текстовом формате
    if 'pgbench_section' in data:
        pgbench_text = data['pgbench_section']
        tps_match = re.search(r'TPS\s*(?:\(Transactions Per Second\))?:\s*([\d.]+)', pgbench_text)
        lat_match = re.search(r'Средняя задержка:\s*([\d.]+)\s*ms', pgbench_text)
        
        if tps_match and lat_match:
            return {
                'TPS_mean': float(tps_match.group(1)),
                'TPS_stdev': 0.0,
                'Latency_Avg_mean': float(lat_match.group(1)),
                'Latency_Avg_stdev': 0.0,
                'samples': 1
            }
    
    # Поиск в результатах fio, где pgbench мог быть запущен отдельно
    if 'fio' in data and any('pgbench' in test_name.lower() for test_name in data['fio'].keys()):
        print(f"⚠️ Обнаружены результаты pgbench в разделе FIO для {data.get('label', 'unknown')}")
    
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
            
            # Добавляем значения на/внутри столбцов
            add_value_labels(ax, bars, values)
        
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
    pgbench_data = {}
    
    for label, data in datasets.items():
        pg_data = extract_pgbench_data(data)
        if pg_data:
            pgbench_data[label] = pg_data
            print(f"✅ Найдены данные pgbench для {label}: TPS={pg_data['TPS_mean']:.1f}, Latency={pg_data['Latency_Avg_mean']:.3f}ms")
        else:
            print(f"⚠️ Не найдены данные pgbench для {label}")
    
    if not pgbench_data:
        print("❌ Не удалось найти данные pgbench ни в одном формате")
        # Создаем пустой файл-заглушку для отладки
        with open(os.path.join(output_dir, 'pgbench_comparison_missing_data.txt'), 'w') as f:
            f.write("Данные pgbench отсутствуют или не были распознаны\n")
            f.write("Структура полученных данных:\n")
            for label, data in datasets.items():
                f.write(f"\n=== {label} ===\n")
                f.write(json.dumps(data, indent=2, ensure_ascii=False))
        return
    
    print(f"✅ Найдены данные pgbench для {len(pgbench_data)} конфигураций")
    
    # Создаем два графика в одной фигуре
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # График TPS
    x = range(len(pgbench_data))
    width = 0.6
    
    labels = list(pgbench_data.keys())
    tps_values = [data['TPS_mean'] for data in pgbench_data.values()]
    tps_errors = [data['TPS_stdev'] for data in pgbench_data.values()]
    
    storage_types = [get_storage_type(label) for label in labels]
    colors = [get_color_for_storage(st) for st in storage_types]
    
    for i, (label, value, error, color) in enumerate(zip(labels, tps_values, tps_errors, colors)):
        bar = ax1.bar(i, value, width, yerr=error, capsize=10, 
                     color=color, alpha=0.8, label=label)
        
        # Добавляем значение на столбец
        height = bar[0].get_height()
        ax1.text(bar[0].get_x() + bar[0].get_width()/2., height + (height * 0.05),
                f'{height:.0f}',
                ha='center', va='bottom', fontsize=9)
    
    ax1.set_xlabel('Конфигурация', fontsize=12)
    ax1.set_ylabel('TPS (транзакций в секунду)', fontsize=12)
    ax1.set_title('Сравнение производительности PostgreSQL (pgbench)', fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels([label.replace('_','-') for label in labels], rotation=15, ha='center')
    ax1.grid(axis='y', alpha=0.3)
    
    # График задержки
    lat_values = [data['Latency_Avg_mean'] for data in pgbench_data.values()]
    lat_errors = [data['Latency_Avg_stdev'] for data in pgbench_data.values()]
    
    for i, (label, value, error, color) in enumerate(zip(labels, lat_values, lat_errors, colors)):
        bar = ax2.bar(i, value, width, yerr=error, capsize=10,
                     color=color, alpha=0.8, label=label)
        
        # Добавляем значение на столбец
        height = bar[0].get_height()
        ax2.text(bar[0].get_x() + bar[0].get_width()/2., height + (height * 0.05),
                f'{height:.2f}',
                ha='center', va='bottom', fontsize=9)
    
    ax2.set_xlabel('Конфигурация', fontsize=12)
    ax2.set_ylabel('Средняя задержка (ms)', fontsize=12)
    ax2.set_title('Сравнение задержек PostgreSQL (pgbench)', fontsize=14, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels([label.replace('_','-') for label in labels], rotation=15, ha='center')
    ax2.grid(axis='y', alpha=0.3)
    
    # Создаем легенду с уникальными типами хранилищ
    unique_types = {}
    for label, st in zip(labels, storage_types):
        vm_match = re.search(r'_(\d+)vms_', label)
        vm_count = vm_match.group(1) if vm_match else "?"
        unique_types[f"{st.upper()} ({vm_count} VM)"] = get_color_for_storage(st)
    
    legend_elements = [plt.Rectangle((0,0),1,1, color=color, alpha=0.8) 
                      for color in unique_types.values()]
    ax1.legend(legend_elements, unique_types.keys(), title='Тип хранилища')
    
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

def debug_dataset_structure(datasets, output_dir):
    """Сохраняет полную структуру данных для отладки"""
    debug_file = os.path.join(output_dir, 'data_structure_debug.txt')
    with open(debug_file, 'w') as f:
        f.write("="*80 + "\n")
        f.write("СТРУКТУРА ДАННЫХ ДЛЯ ВИЗУАЛИЗАЦИИ\n")
        f.write("="*80 + "\n\n")
        
        for label, data in datasets.items():
            f.write(f"=== {label} ===\n")
            f.write(f"Тип данных: {type(data)}\n")
            
            if isinstance(data, dict):
                f.write("Ключи верхнего уровня:\n")
                for key in data.keys():
                    f.write(f"  - {key}\n")
                
                # Структура FIO данных
                if 'fio' in data and isinstance(data['fio'], dict):
                    f.write("\nFIO тесты:\n")
                    for test_name, metrics in data['fio'].items():
                        f.write(f"  - {test_name}: {', '.join(metrics.keys())}\n")
                        f.write(f"    Значения: {json.dumps(metrics, indent=6)}\n")
                
                # Структура pgbench данных
                if 'pgbench' in data:
                    f.write("\npgbench данные:\n")
                    f.write(f"  {json.dumps(data['pgbench'], indent=4)}\n")
                elif 'pgbench_section' in data:
                    f.write("\npgbench_section (текст):\n")
                    f.write(f"  {data['pgbench_section'][:200]}...\n")
            
            f.write("\n" + "="*80 + "\n")
    
    print(f"🔍 Структура данных сохранена для отладки: {debug_file}")

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
    
    # Отладочная информация о структуре данных
    debug_dataset_structure(valid_datasets, "visualization_output")
    
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