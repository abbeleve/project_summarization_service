import { useState, useEffect } from 'react';
import { useTheme } from '@/context/ThemeContext';
import {
  TRANSCRIBE_CONFIG,
  DIARIZATION_CONFIG,
  LLM_MODELS,
  DEFAULT_SETTINGS,
  getTranscribeModelsByLib,
  getDiarizationModelsByLib,
} from '@/config/settings';
import type { ProcessingSettings } from '@/types/transcript';

const loadSavedSettings = (): ProcessingSettings => {
  try {
    const saved = localStorage.getItem('modelSettings');
    return saved ? JSON.parse(saved) : { ...DEFAULT_SETTINGS };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
};

export const SettingsPage = () => {
  const { theme, toggleTheme } = useTheme();
  const [settings, setSettings] = useState<ProcessingSettings>(loadSavedSettings);
  const saved = loadSavedSettings();
  const [showSaved, setShowSaved] = useState(false);

  const hasChanges = JSON.stringify(settings) !== JSON.stringify(saved);

  useEffect(() => {
    if (showSaved) {
      const t = setTimeout(() => setShowSaved(false), 2000);
      return () => clearTimeout(t);
    }
  }, [showSaved]);

  const handleSave = () => {
    localStorage.setItem('modelSettings', JSON.stringify(settings));
    setShowSaved(true);
  };

  return (
    <div className="max-w-4xl mx-auto px-6 py-10 pb-24">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-8">Настройки</h1>

      <div className="space-y-6">
        {/* Тема */}
        <div className="bg-white dark:bg-dark-base-800 rounded-2xl p-6 border border-gray-200 dark:border-dark-base-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Оформление</h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Тёмная тема</p>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Переключение между светлой и тёмной темой</p>
            </div>
            <button
              onClick={toggleTheme}
              className={`relative w-14 h-7 rounded-full transition-colors cursor-pointer ${
                theme === 'dark' ? 'bg-blue-600' : 'bg-gray-300'
              }`}
            >
              <span className={`absolute top-0.5 left-0.5 w-6 h-6 bg-white rounded-full shadow-md transition-transform flex items-center justify-center text-xs ${
                theme === 'dark' ? 'translate-x-7' : ''
              }`}>
                {theme === 'dark' ? '🌙' : '☀️'}
              </span>
            </button>
          </div>
        </div>

        {/* Настройки моделей */}
        <div className="bg-white dark:bg-dark-base-800 rounded-2xl p-6 border border-gray-200 dark:border-dark-base-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Настройки моделей</h2>

          <div className="space-y-5">
            {/* Библиотека транскрибации */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-1.5">
                Библиотека транскрибации
              </label>
              <select
                value={settings.transcribeLib}
                onChange={(e) => {
                  const lib = e.target.value;
                  const models = getTranscribeModelsByLib(lib);
                  setSettings(s => ({
                    ...s,
                    transcribeLib: lib,
                    transcribeModel: models[0] || s.transcribeModel
                  }));
                }}
                className="w-full border border-gray-300 dark:border-dark-base-600 rounded-xl px-4 py-2.5 text-base font-medium text-gray-900 dark:text-white bg-white dark:bg-dark-base-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {Object.keys(TRANSCRIBE_CONFIG).map(lib => (
                  <option key={lib} value={lib}>{lib}</option>
                ))}
              </select>
            </div>

            {/* Модель транскрибации */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-1.5">
                Модель транскрибации
              </label>
              <select
                value={settings.transcribeModel}
                onChange={(e) => setSettings(s => ({ ...s, transcribeModel: e.target.value }))}
                className="w-full border border-gray-300 dark:border-dark-base-600 rounded-xl px-4 py-2.5 text-base font-medium text-gray-900 dark:text-white bg-white dark:bg-dark-base-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {getTranscribeModelsByLib(settings.transcribeLib).map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </div>

            {/* Библиотека диаризации */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-1.5">
                Библиотека диаризации
              </label>
              <select
                value={settings.diarizeLib}
                onChange={(e) => {
                  const lib = e.target.value;
                  const models = getDiarizationModelsByLib(lib);
                  setSettings(s => ({
                    ...s,
                    diarizeLib: lib,
                    diarizationModel: models[0] || s.diarizationModel
                  }));
                }}
                className="w-full border border-gray-300 dark:border-dark-base-600 rounded-xl px-4 py-2.5 text-base font-medium text-gray-900 dark:text-white bg-white dark:bg-dark-base-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {Object.keys(DIARIZATION_CONFIG).map(lib => (
                  <option key={lib} value={lib}>{lib}</option>
                ))}
              </select>
            </div>

            {/* Модель диаризации */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-1.5">
                Модель диаризации
              </label>
              <select
                value={settings.diarizationModel}
                onChange={(e) => setSettings(s => ({ ...s, diarizationModel: e.target.value }))}
                className="w-full border border-gray-300 dark:border-dark-base-600 rounded-xl px-4 py-2.5 text-base font-medium text-gray-900 dark:text-white bg-white dark:bg-dark-base-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {getDiarizationModelsByLib(settings.diarizeLib).map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </div>

            {/* LLM модель */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-1.5">
                Модель LLM (суммаризация)
              </label>
              <select
                value={settings.llmModel}
                onChange={(e) => setSettings(s => ({ ...s, llmModel: e.target.value }))}
                className="w-full border border-gray-300 dark:border-dark-base-600 rounded-xl px-4 py-2.5 text-base font-medium text-gray-900 dark:text-white bg-white dark:bg-dark-base-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {LLM_MODELS.map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Язык (заглушка) */}
        <div className="bg-white dark:bg-dark-base-800 rounded-2xl p-6 border border-gray-200 dark:border-dark-base-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Язык</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">Русский (системный)</p>
        </div>
      </div>

      {/* Кнопка сохранения — по центру относительно настроек */}
      {hasChanges && (
        <div className="flex justify-center pt-6">
          <button
            onClick={handleSave}
            className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all cursor-pointer"
          >
            {showSaved ? '✓ Сохранено' : 'Сохранить настройки'}
          </button>
        </div>
      )}
    </div>
  );
};