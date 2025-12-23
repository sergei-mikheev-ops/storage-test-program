#!/usr/bin/env python3
"""
Исправленный скрипт для агрегации результатов тестирования с валидацией данных
"""
import os
import re
import json
import sys
from pathlib import Path
from statistics import mean, stdev
from datetime import datetime

def validate_fio_data(test_name, iops, bandwidth, latency):
    """Проверяет физическую корректность данных fio"""
    # Проверка соотношения IOPS и Bandwidth для 4k блока
    expected_bandwidth = iops * 4  # 4k блок = 4 KiB
    
    # Допустимое отклонение 20%
    min_allowed = expected_bandwidth * 0.8
    max_allowed = expected_bandwidth * 1.2
    
    # Исключения для операций записи (может быть меньше из-за кэширования)
    write_exceptions = ["Write", "RW (Write)"]
    if any(exc in test_name for exc in write_exceptions):
        min_allowed = expected_bandwidth * 0.5
    
    # Фильтрация явно аномальных значений
    if (iops > 100000 or bandwidth > 10000 or 
        (bandwidth > 0 and iops > 0 and not (min_allowed <= bandwidth <= max_allowed))):
        print(f"⚠️ Аномальные данные для '{test_name}': IOPS={iops:.1f}, Bandwidth={bandwidth:.1f}")
        print(f"   Ожидаемый диапазон bandwidth: {min_allowed:.1f}-{max_allowed:.1f}")
        return False
    
    # Проверка задержек
    max_allowed_latency = {
        "Sequential Read": 50,
        "Sequential Write": 100,
        "Random Read": 100,
        "Random Write": 200,
        "Mixed RW": 200
    }
    
    # Определение типа теста
    test_type = "Mixed RW" if "Mixed RW" in test_name else test_name.split()[0]
    max_latency = max_allowed_latency.get(test_type, 300)  # значение по умолчанию
    
    if latency > max_latency:
        print(f"⚠️ Аномальная задержка для '{test_name}': {latency:.2f}ms (макс. допустимая: {max_latency}ms)")
        return False
    
    return True

def parse_results_sheet(file_path):
    """Улучшенный парсер результатов с валидацией данных"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        results = {'fio': {}, 'pgbench': {}, 'pgbench_section': ''}
        
        # Улучшенный парсинг результатов fio
        fio_pattern = r'(\d+)\s+(.+?)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)'
        for match in re.finditer(fio_pattern, content):
            test_num = int(match.group(1))
            test_name = match.group(2).strip()
            iops = float(match.group(3))
            bandwidth = float(match.group(4))
            latency = float(match.group(5))
            
            # Валидация данных
            if validate_fio_data(test_name, iops, bandwidth, latency):
                # Уникальный ключ для тестов с одинаковыми номерами
                unique_key = test_name
                if "Mixed RW" in test_name:
                    # Определяем тип операции по содержимому строки
                    if "Read" in test_name or "Чтение" in test_name:
                        unique_key = "Mixed RW (Read)"
                    elif "Write" in test_name or "Запись" in test_name:
                        unique_key = "Mixed RW (Write)"
                
                results['fio'][unique_key] = {
                    'IOPS': iops,
                    'Bandwidth': bandwidth,
                    'Latency': latency
                }
        
        # Парсинг результатов pgbench
        pgbench_match = re.search(
            r'TPS\s*\(Transactions Per Second\):\s*([\d.]+).*?Средняя задержка:\s*([\d.]+).*?Обработано транзакций:\s*(\d+)',
            content, re.DOTALL
        )
        if pgbench_match:
            results['pgbench'] = {
                'TPS': float(pgbench_match.group(1)),
                'Latency_Avg': float(pgbench_match.group(2)),
                'Transactions': int(pgbench_match.group(3)),
                'samples': 1
            }
            # Сохраняем и текстовую секцию для отладки
            pgbench_section_match = re.search(r'===+Результаты pgbench.*?(===+|$)', content, re.DOTALL)
            if pgbench_section_match:
                results['pgbench_section'] = pgbench_section_match.group(0)
        
        return results
    except Exception as e:
        print(f"❌ Ошибка парсинга {file_path}: {str(e)}")
        return None

def get_vm_count_from_path(file_path):
    """Определяет количество ВМ из пути к файлу результатов"""
    path_str = str(file_path)
    match = re.search(r'_(\d+)vms_', path_str)
    if match:
        return int(match.group(1))
    return 1  # значение по умолчанию

def aggregate_results(results_dir):
    """Агрегирует результаты с корректной обработкой разных конфигураций"""
    results_dir = Path(results_dir)
    all_result_files = list(results_dir.rglob('results_sheet_*.txt'))
    
    if not all_result_files:
        print("❌ Не найдено файлов результатов")
        print(f"🔍 Проверьте содержимое директории {results_dir}:")
        for item in results_dir.rglob('*'):
            if item.is_file():
                print(f"  • {item.relative_to(results_dir)}")
        return None
    
    print(f"✅ Найдено {len(all_result_files)} файлов результатов")
    iterations_data = {}
    
    for file in all_result_files:
        # Извлекаем номер итерации из имени файла
        iter_match = re.search(r'iter(\d+)', file.name)
        if not iter_match:
            continue
        
        iter_num = int(iter_match.group(1))
        parsed = parse_results_sheet(file)
        if parsed:
            if iter_num not in iterations_data:
                iterations_data[iter_num] = []
            iterations_data[iter_num].append(parsed)
    
    if not iterations_data:
        print("❌ Не удалось распарсить результаты")
        return None
    
    # Определяем количество ВМ из пути к директории
    vm_count = get_vm_count_from_path(results_dir)
    print(f"ℹ️ Определено количество ВМ: {vm_count}")
    
    # Агрегация FIO
    aggregated = {'fio': {}, 'pgbench': {}, 'iterations': sorted(iterations_data.keys()), 'num_vms': vm_count}
    all_fio_tests = set()
    
    for iter_results in iterations_data.values():
        for vm_result in iter_results:
            all_fio_tests.update(vm_result['fio'].keys())
    
    for test_name in sorted(all_fio_tests):
        metrics = {'IOPS': [], 'Bandwidth': [], 'Latency': []}
        for iter_results in iterations_data.values():
            for vm_result in iter_results:
                if test_name in vm_result['fio']:
                    metrics['IOPS'].append(vm_result['fio'][test_name]['IOPS'])
                    metrics['Bandwidth'].append(vm_result['fio'][test_name]['Bandwidth'])
                    metrics['Latency'].append(vm_result['fio'][test_name]['Latency'])
        
        if metrics['IOPS']:  # если есть данные для этого теста
            samples = len(metrics['IOPS'])
            aggregated['fio'][test_name] = {
                'IOPS_mean': mean(metrics['IOPS']),
                'IOPS_stdev': stdev(metrics['IOPS']) if samples > 1 else 0,
                'Bandwidth_mean': mean(metrics['Bandwidth']),
                'Bandwidth_stdev': stdev(metrics['Bandwidth']) if samples > 1 else 0,
                'Latency_mean': mean(metrics['Latency']),
                'Latency_stdev': stdev(metrics['Latency']) if samples > 1 else 0,
                'samples': samples
            }
    
    # Агрегация pgbench
    pgbench_metrics = {'TPS': [], 'Latency_Avg': [], 'Transactions': []}
    pgbench_found = False
    
    for iter_results in iterations_data.values():
        for vm_result in iter_results:
            if 'pgbench' in vm_result and vm_result['pgbench']:
                pgbench_found = True
                pgbench_metrics['TPS'].append(vm_result['pgbench']['TPS'])
                if vm_result['pgbench']['Latency_Avg'] is not None:
                    pgbench_metrics['Latency_Avg'].append(vm_result['pgbench']['Latency_Avg'])
                pgbench_metrics['Transactions'].append(vm_result['pgbench']['Transactions'])
    
    if pgbench_found and pgbench_metrics['TPS']:
        samples = len(pgbench_metrics['TPS'])
        aggregated['pgbench'] = {
            'TPS_mean': mean(pgbench_metrics['TPS']),
            'TPS_stdev': stdev(pgbench_metrics['TPS']) if samples > 1 else 0,
            'Latency_Avg_mean': mean(pgbench_metrics['Latency_Avg']) if pgbench_metrics['Latency_Avg'] else 0,
            'Latency_Avg_stdev': stdev(pgbench_metrics['Latency_Avg']) if samples > 1 and pgbench_metrics['Latency_Avg'] else 0,
            'samples': samples
        }
    
    return aggregated

def debug_data_structure(aggregated_data, output_file):
    """Отображает структуру агрегированных данных для диагностики"""
    print("\n🔍 Структура агрегированных данных:")
    print(f"  • Тип данных: {type(aggregated_data)}")
    
    if isinstance(aggregated_data, dict):
        print(f"  • Ключи верхнего уровня: {', '.join(aggregated_data.keys())}")
        
        if 'fio' in aggregated_data:
            print(f"  • Тесты FIO: {', '.join(aggregated_data['fio'].keys())}")
            for test_name, metrics in aggregated_data['fio'].items():
                print(f"    - {test_name}: {', '.join(metrics.keys())}")
        
        if 'pgbench' in aggregated_data:
            print(f"  • Данные pgbench: {', '.join(aggregated_data['pgbench'].keys())}")
        elif 'pgbench_section' in aggregated_data:
            print("  • Найдены данные pgbench в текстовом формате")
    
    # Сохраняем полную структуру в файл для анализа
    with open(f"{output_file}_structure_debug.txt", 'w') as f:
        json.dump(aggregated_data, f, indent=2, ensure_ascii=False)
    
    print(f"  • Полная структура сохранена в: {output_file}_structure_debug.txt")

def generate_report(aggregated, output_file):
    """Генерирует отчет с детальной информацией о валидации данных"""
    report = []
    report.append("="*80)
    report.append("АГРЕГИРОВАННЫЕ РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    report.append("="*80)
    report.append(f"Дата создания отчета: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Количество итераций: {len(aggregated['iterations'])}")
    report.append(f"Количество ВМ: {aggregated['num_vms']}")
    report.append("")
    report.append("ℹ️  ВНИМАНИЕ: Аномальные данные были автоматически отфильтрованы")
    report.append("")
    
    # FIO результаты
    if aggregated['fio']:
        report.append("="*80)
        report.append("FIO - Тестирование дисковой подсистемы (средние значения)")
        report.append("="*80)
        report.append("")
        report.append(f"{'Test Name':<35} {'IOPS_mean':<15} {'Bandwidth_mean (MiB/s)':<25} {'Latency_mean (ms)':<20} {'Samples':<8}")
        report.append("-"*80)
        for test_name, metrics in sorted(aggregated['fio'].items()):
            report.append(
                f"{test_name:<35} "
                f"{metrics['IOPS_mean']:>7.1f} ± {metrics['IOPS_stdev']:>4.1f}    "
                f"{metrics['Bandwidth_mean']:>7.1f} ± {metrics['Bandwidth_stdev']:>4.1f}                   "
                f"{metrics['Latency_mean']:>6.2f} ± {metrics['Latency_stdev']:>4.2f}           "
                f"{metrics['samples']:<8}"
            )
        report.append("")
    
    # pgbench результаты
    if 'pgbench' in aggregated and aggregated['pgbench']:
        report.append("="*80)
        report.append("pgbench - Тестирование PostgreSQL OLTP (средние значения)")
        report.append("="*80)
        report.append("")
        pg = aggregated['pgbench']
        report.append(f"TPS (Transactions Per Second): {pg['TPS_mean']:.2f} ± {pg['TPS_stdev']:.2f}")
        report.append(f"Средняя задержка: {pg['Latency_Avg_mean']:.3f} ± {pg['Latency_Avg_stdev']:.3f} ms")
        report.append(f"Количество измерений: {pg['samples']}")
        report.append("")
    
    report.append("="*80)
    report.append("Примечание: Значения указаны в формате 'среднее ± стандартное отклонение'")
    report.append("Аномальные данные (несоответствующие физическим ограничениям) были отфильтрованы")
    report.append("="*80)
    
    report_text = "\n".join(report)
    
    # Вывод в консоль
    print(report_text)
    
    # Сохранение в файл
    with open(output_file, 'w') as f:
        f.write(report_text)
    print(f"\n📄 Отчет сохранен: {output_file}")
    return report_text

def save_json(aggregated, output_file):
    """Сохраняет агрегированные данные в JSON с информацией о фильтрации"""
    with open(output_file, 'w') as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False)
    print(f"📊 JSON данные сохранены: {output_file}")

def main():
    if len(sys.argv) < 2:
        print("Использование: python3 aggregate_results.py <путь_к_директории_с_результатами> [путь_2] ...")
        print("\nПримеры:")
        print("  python3 aggregate_results.py results/20251218_1619_local_1vms_2iter/")
        print("  python3 aggregate_results.py results/*/")
        sys.exit(1)
    
    # Обработка нескольких директорий
    for results_dir in sys.argv[1:]:
        if not os.path.exists(results_dir):
            print(f"❌ Директория не найдена: {results_dir}")
            continue
        
        print(f"\n{'='*60}")
        print(f"📁 Анализ результатов в: {results_dir}")
        print("⏳ Обработка данных...")
        
        aggregated = aggregate_results(results_dir)
        if not aggregated:
            print("❌ Не удалось агрегировать результаты")
            continue
        
        # Отладочная информация о структуре данных
        debug_data_structure(aggregated, os.path.join(results_dir, "aggregated_report"))
        
        # Генерация отчетов
        output_base = os.path.join(results_dir, "aggregated_report")
        generate_report(aggregated, f"{output_base}.txt")
        save_json(aggregated, f"{output_base}.json")
    
    print(f"\n{'='*60}")
    print("✅ Агрегация завершена для всех директорий!")

if __name__ == "__main__":
    main()