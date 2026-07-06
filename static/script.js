const display = document.getElementById('display');
const historyList = document.getElementById('history-list');

function append(value) {
  display.value += value;
}

function clearDisplay() {
  display.value = '';
}

function deleteLast() {
  display.value = display.value.slice(0, -1);
}

async function calculate() {
  const expression = display.value.trim();
  if (!expression) return;

  try {
    const response = await fetch('/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ expression }),
    });

    const data = await response.json();

    if (!response.ok) {
      display.value = 'Error';
      setTimeout(() => (display.value = ''), 1200);
      return;
    }

    display.value = data.result;
    addToHistory(data.expression, data.result);
  } catch (err) {
    display.value = 'Error';
    setTimeout(() => (display.value = ''), 1200);
  }
}

function addToHistory(expression, result) {
  const emptyItem = historyList.querySelector('.empty');
  if (emptyItem) emptyItem.remove();

  const li = document.createElement('li');
  li.textContent = `${expression} = ${result}`;
  historyList.prepend(li);
}

document.addEventListener('keydown', (e) => {
  if (e.key >= '0' && e.key <= '9') append(e.key);
  else if (['+', '-', '*', '/', '(', ')', '.'].includes(e.key)) append(e.key);
  else if (e.key === 'Enter') calculate();
  else if (e.key === 'Backspace') deleteLast();
  else if (e.key === 'Escape') clearDisplay();
});
