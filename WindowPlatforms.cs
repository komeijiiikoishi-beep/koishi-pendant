using System;
using System.Runtime.InteropServices;

namespace PendantPhysics
{
    public static class WindowPlatforms
    {
        [DllImport("user32.dll")]
        private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
        [DllImport("user32.dll")]
        private static extern bool IsWindowVisible(IntPtr hWnd);
        [DllImport("user32.dll")]
        private static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
        [DllImport("user32.dll")]
        private static extern IntPtr GetWindow(IntPtr hWnd, uint uCmd);
        [DllImport("user32.dll")]
        private static extern long GetWindowLongPtr(IntPtr hWnd, int nIndex);
        [DllImport("user32.dll", SetLastError = true)]
        private static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
        [DllImport("user32.dll", SetLastError = true)]
        private static extern IntPtr FindWindowEx(IntPtr hWndParent, IntPtr hWndChildAfter, string lpClassName, string lpWindowName);

        private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
        [StructLayout(LayoutKind.Sequential)]
        private struct RECT { public int Left, Top, Right, Bottom; }

        private const uint GW_OWNER = 4;
        private const int GWL_STYLE = -16;
        private const int GWL_EXSTYLE = -20;
        private const long WS_CHILD = 0x40000000;
        private const long WS_EX_TOOLWINDOW = 0x00000080;
        private const long WS_EX_APPWINDOW = 0x00040000;

        private static float[] _platLeft = new float[32];
        private static float[] _platRight = new float[32];
        private static float[] _platTop = new float[32];
        private static int _platCount = 0;
        private static int _frameCounter = 999;
        private const int RefreshInterval = 30;
        private const int TitleBarHeight = 36;
        private const int MinWindowW = 200;
        private const int MinWindowH = 100;
        // Taskbar is typically 40-48px tall, treat the whole bar as platform
        private const int TaskBarPlatformHeight = 40;

        public static int GetCount() { return _platCount; }
        public static float GetLeft(int i) { return _platLeft[i]; }
        public static float GetRight(int i) { return _platRight[i]; }
        public static float GetTop(int i) { return _platTop[i]; }

        public static bool Update()
        {
            _frameCounter++;
            if (_frameCounter < RefreshInterval) return false;
            _frameCounter = 0;
            Refresh();
            return true;
        }

        private static void Refresh()
        {
            _platCount = 0;
            EnumWindows(EnumCallback, IntPtr.Zero);
            // Detect taskbars — these are not enumerated by EnumWindows filter
            AddTaskbarPlatforms();
        }

        private static void AddTaskbarPlatforms()
        {
            // Primary taskbar
            IntPtr hPrimary = FindWindow("Shell_TrayWnd", null);
            if (hPrimary != IntPtr.Zero)
                AddWindowAsPlatform(hPrimary, TaskBarPlatformHeight);

            // Secondary taskbars (multi-monitor)
            IntPtr hSecondary = IntPtr.Zero;
            while (true)
            {
                hSecondary = FindWindowEx(IntPtr.Zero, hSecondary, "Shell_SecondaryTrayWnd", null);
                if (hSecondary == IntPtr.Zero) break;
                AddWindowAsPlatform(hSecondary, TaskBarPlatformHeight);
            }
        }

        private static void AddWindowAsPlatform(IntPtr hWnd, int topOffset)
        {
            if (_platCount >= 32) return;
            RECT r;
            if (!GetWindowRect(hWnd, out r)) return;
            int w = r.Right - r.Left;
            int h = r.Bottom - r.Top;
            if (w < 100 || h < 10) return;
            _platLeft[_platCount] = r.Left;
            _platRight[_platCount] = r.Right;
            _platTop[_platCount] = r.Top + Math.Min(topOffset, h);
            _platCount++;
        }

        private static bool EnumCallback(IntPtr hWnd, IntPtr lParam)
        {
            if (_platCount >= 32) return false;
            if (!IsWindowVisible(hWnd)) return true;
            if (GetWindow(hWnd, GW_OWNER) != IntPtr.Zero) return true;
            long style = GetWindowLongPtr(hWnd, GWL_STYLE);
            if ((style & WS_CHILD) != 0) return true;
            long exStyle = GetWindowLongPtr(hWnd, GWL_EXSTYLE);
            if ((exStyle & WS_EX_TOOLWINDOW) != 0 && (exStyle & WS_EX_APPWINDOW) == 0) return true;
            RECT r;
            if (!GetWindowRect(hWnd, out r)) return true;
            int w = r.Right - r.Left;
            int h = r.Bottom - r.Top;
            if (w < MinWindowW || h < MinWindowH) return true;
            int tbH = Math.Min(TitleBarHeight, h / 5);
            _platLeft[_platCount] = r.Left;
            _platRight[_platCount] = r.Right;
            _platTop[_platCount] = r.Top + tbH;
            _platCount++;
            return true;
        }
    }
}
