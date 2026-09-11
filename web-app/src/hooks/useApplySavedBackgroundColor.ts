import { useEffect } from 'react';

/** 启动时根据 localStorage 中的 backgroundColor 应用到布局相关节点 */
export function useApplySavedBackgroundColor() {
  useEffect(() => {
    const savedColor = localStorage.getItem('backgroundColor');
    if (!savedColor) return;

    document.body.style.backgroundColor = savedColor;

    document.querySelectorAll('.min-h-screen').forEach((div) => {
      div.classList.remove('bg-gray-50');
      (div as HTMLElement).style.backgroundColor = savedColor;
    });

    const mainElement = document.querySelector('main');
    if (mainElement) {
      (mainElement as HTMLElement).style.backgroundColor = savedColor;
    }

    const mainDiv = document.querySelector('main > div');
    if (mainDiv) {
      (mainDiv as HTMLElement).style.backgroundColor = savedColor;
    }

    document.querySelectorAll('.card').forEach((card) => {
      card.classList.remove('bg-white');
      (card as HTMLElement).style.backgroundColor = '#ffffff';
    });

    document.querySelectorAll('.max-w-7xl.mx-auto').forEach((container) => {
      (container as HTMLElement).style.backgroundColor = savedColor;
    });
  }, []);
}
