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
import { crmApi } from '@/api/crm';

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

  // ===== CRM (Weeek) =====
  const [crmStatus, setCrmStatus] = useState<boolean | null>(null);
  const [crmToken, setCrmToken] = useState('');
  const [crmSaving, setCrmSaving] = useState(false);
  const [crmFeedback, setCrmFeedback] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadCrmStatus = async () => {
    try {
      const status = await crmApi.getStatus();
      setCrmStatus(status.connected);
    } catch {
      setCrmStatus(false);
    }
  };

  useEffect(() => {
    loadCrmStatus();
  }, []);

  useEffect(() => {
    if (!crmFeedback) return;
    const t = setTimeout(() => setCrmFeedback(null), 3000);
    return () => clearTimeout(t);
  }, [crmFeedback]);

  const handleCRMConnect = async () => {
    if (!crmToken.trim()) {
      setCrmFeedback({ type: 'error', text: 'Введите API токен' });
      return;
    }
    setCrmSaving(true);
    try {
      const res = await crmApi.connect(crmToken.trim());
      if (res.status === 'ok') {
        setCrmFeedback({ type: 'success', text: 'CRM подключена' });
        setCrmToken('');
        setCrmStatus(true);
      } else {
        setCrmFeedback({ type: 'error', text: res.message || 'Не удалось подключить CRM' });
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Ошибка подключения';
      setCrmFeedback({ type: 'error', text: msg });
    } finally {
      setCrmSaving(false);
    }
  };

  const handleCRMDisconnect = async () => {
    setCrmSaving(true);
    try {
      const res = await crmApi.disconnect();
      if (res.status === 'ok') {
        setCrmFeedback({ type: 'success', text: 'CRM отключена' });
        setCrmStatus(false);
      } else {
        setCrmFeedback({ type: 'error', text: res.message || 'Не удалось отключить CRM' });
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Ошибка отключения';
      setCrmFeedback({ type: 'error', text: msg });
    } finally {
      setCrmSaving(false);
    }
  };

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

        {/* Интеграция с CRM (Weeek) */}
        <div className="bg-white dark:bg-dark-base-800 rounded-2xl p-6 border border-gray-200 dark:border-dark-base-700">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Интеграция с CRM (Weeek)
            </h2>
            {crmStatus === true && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 text-xs font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                Подключено
              </span>
            )}
            {crmStatus === false && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-gray-100 dark:bg-gray-800/40 text-gray-600 dark:text-gray-400 text-xs font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
                Не подключено
              </span>
            )}
          </div>

          <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
            Позволяет отправлять задачи из совещаний в Weeek. Токен шифруется и хранится
            на сервере. Получить токен можно в{' '}
            <a
              href="https://app.weeek.net/settings/api"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 dark:text-blue-400 hover:underline"
            >
              настройках Weeek → API
            </a>
            .
          </p>

          {crmStatus === true ? (
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm text-gray-700 dark:text-gray-300">
                API токен Weeek сохранён и используется для отправки задач.
              </p>
              <button
                onClick={handleCRMDisconnect}
                disabled={crmSaving}
                className="px-4 py-2 rounded-xl text-sm font-semibold bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/30 border border-red-200 dark:border-red-800/40 disabled:opacity-50 disabled:cursor-wait transition-colors cursor-pointer"
              >
                {crmSaving ? 'Отключение…' : 'Отключить'}
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-1.5">
                  API токен
                </label>
                <input
                  type="password"
                  value={crmToken}
                  onChange={(e) => setCrmToken(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleCRMConnect();
                  }}
                  placeholder="wk_xxxxxxxxxxxxxxxxxxxxxxxx"
                  autoComplete="off"
                  spellCheck={false}
                  className="w-full border border-gray-300 dark:border-dark-base-600 rounded-xl px-4 py-2.5 text-base font-mono text-gray-900 dark:text-white bg-white dark:bg-dark-base-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="flex justify-end">
                <button
                  onClick={handleCRMConnect}
                  disabled={crmSaving || !crmToken.trim()}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {crmSaving ? 'Подключение…' : 'Подключить'}
                </button>
              </div>
            </div>
          )}

          {crmFeedback && (
            <p
              className={`mt-3 text-xs font-medium ${
                crmFeedback.type === 'success'
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : 'text-red-600 dark:text-red-400'
              }`}
            >
              {crmFeedback.type === 'success' ? '✓ ' : '✗ '}
              {crmFeedback.text}
            </p>
          )}
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