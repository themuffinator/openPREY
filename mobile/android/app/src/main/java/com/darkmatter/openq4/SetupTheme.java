// SPDX-License-Identifier: GPL-3.0-or-later
package com.darkmatter.openq4;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Canvas;
import android.graphics.ColorFilter;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.view.Gravity;
import android.view.MotionEvent;
import android.widget.Button;
import android.widget.TextView;

/** Native setup uses the same Marine faces and open, cut action plates as the game UI. */
final class SetupTheme {
    static final int BACKGROUND = 0xff090d09, TEXT = 0xffcccccc, AMBER = 0xffeaa944;
    final Context context;
    final Typeface title, body;

    SetupTheme(Context context) {
        this.context = context;
        title = Typeface.createFromAsset(context.getAssets(), "fonts/marine.ttf");
        body = Typeface.createFromAsset(context.getAssets(), "fonts/lowpixel.ttf");
    }

    int dp(float value) { return Math.round(value * context.getResources().getDisplayMetrics().density); }

    TextView text(int resource, boolean heading) {
        TextView view = new TextView(context);
        view.setText(resource);
        view.setTypeface(heading ? title : body);
        view.setTextSize(heading ? 24 : 17);
        view.setTextColor(heading ? 0xffaaaaaa : TEXT);
        view.setPadding(0, dp(8), 0, dp(8));
        if (heading && android.os.Build.VERSION.SDK_INT >= 28) view.setAccessibilityHeading(true);
        return view;
    }

    Button button(int resource, Runnable action) {
        Button button = new TouchButton(context, dp(8));
        button.setText(resource);
        button.setAllCaps(false);
        button.setTypeface(title);
        button.setTextSize(18);
        button.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
        button.setMinHeight(dp(48));
        button.setMinimumHeight(dp(48));
        button.setPaddingRelative(dp(36), dp(10), dp(16), dp(10));
        button.setTextColor(new ColorStateList(new int[][] {
            {-android.R.attr.state_enabled}, {android.R.attr.state_pressed},
            {android.R.attr.state_focused}, {android.R.attr.state_hovered}, {}
        }, new int[] {0xff686d60, 0xffff9900, 0xffff9900, 0xffff9900, TEXT}));
        button.setBackground(new Plate(dp(1), dp(18), dp(7),
            context.getResources().getConfiguration().getLayoutDirection() == android.view.View.LAYOUT_DIRECTION_RTL));
        button.setStateListAnimator(null);
        button.setOnClickListener(view -> action.run());
        return button;
    }

    private static final class TouchButton extends Button {
        private final float slop;
        private float x, y;
        private int pointer = -1;
        private boolean cancelled;
        TouchButton(Context context, float slop) { super(context); this.slop = slop; }
        @Override public boolean performClick() {
            // Keep keyboard, controller and accessibility activation on the
            // ordinary Button path; only touch movement has a custom policy.
            return super.performClick();
        }
        @Override public boolean onTouchEvent(MotionEvent event) {
            int action = event.getActionMasked();
            if (action == MotionEvent.ACTION_DOWN) {
                pointer = event.getPointerId(0); x = event.getX(); y = event.getY(); cancelled = false;
                if (isEnabled() && event.getToolType(0) == MotionEvent.TOOL_TYPE_FINGER)
                    performHapticFeedback(android.view.HapticFeedbackConstants.VIRTUAL_KEY);
            } else if (action == MotionEvent.ACTION_POINTER_DOWN) return true;
            else if (action == MotionEvent.ACTION_POINTER_UP && event.getPointerId(event.getActionIndex()) != pointer) return true;
            int index = event.findPointerIndex(pointer);
            if (!cancelled && (index < 0 || action == MotionEvent.ACTION_CANCEL || action == MotionEvent.ACTION_POINTER_UP ||
                    (action == MotionEvent.ACTION_UP && (event.getX(index) < 0 || event.getY(index) < 0 ||
                                                        event.getX(index) >= getWidth() || event.getY(index) >= getHeight())) ||
                    Math.hypot(event.getX(index) - x, event.getY(index) - y) > slop)) {
                cancelled = true;
                MotionEvent cancel = MotionEvent.obtain(event);
                cancel.setAction(MotionEvent.ACTION_CANCEL);
                super.onTouchEvent(cancel);
                cancel.recycle();
            }
            if (cancelled) return true;
            return super.onTouchEvent(event);
        }
    }

    private static final class Plate extends Drawable {
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final float stroke, cut, marker;
        private final boolean rtl;
        Plate(float stroke, float cut, float marker, boolean rtl) {
            this.stroke = stroke; this.cut = cut; this.marker = marker; this.rtl = rtl;
        }
        @Override public boolean isStateful() { return true; }
        @Override protected boolean onStateChange(int[] state) { invalidateSelf(); return true; }
        @Override public void draw(Canvas canvas) {
            boolean enabled = false, active = false;
            for (int state : getState()) {
                enabled |= state == android.R.attr.state_enabled;
                active |= state == android.R.attr.state_pressed || state == android.R.attr.state_focused || state == android.R.attr.state_hovered;
            }
            float w = getBounds().width(), h = getBounds().height(), c = Math.min(cut, h / 2);
            canvas.save();
            canvas.translate(getBounds().left, getBounds().top);
            if (rtl) { canvas.translate(w, 0); canvas.scale(-1, 1); }
            Path shape = new Path();
            shape.moveTo(stroke, 0); shape.lineTo(w, 0); shape.lineTo(w, h - stroke);
            shape.lineTo(c, h - stroke); shape.lineTo(stroke, h - c); shape.close();
            paint.setStyle(Paint.Style.FILL);
            paint.setShader(new LinearGradient(0, 0, w, 0, enabled ? (active ? 0xb34d5721 : 0x664d5721) : 0x224d5721,
                                               0x004d5721, Shader.TileMode.CLAMP));
            canvas.drawPath(shape, paint);
            Path rail = new Path();
            rail.moveTo(stroke, 0); rail.lineTo(stroke, h - c); rail.lineTo(c, h - stroke); rail.lineTo(w, h - stroke);
            paint.setStyle(Paint.Style.STROKE); paint.setStrokeWidth(stroke);
            canvas.drawPath(rail, paint);
            paint.setStyle(Paint.Style.FILL); paint.setShader(null);
            paint.setColor(enabled && active ? 0xffff9900 : 0x806d7938);
            float start = cut, top = (h - marker) / 2;
            Path triangle = new Path(); triangle.moveTo(start, top); triangle.lineTo(start + marker, top);
            triangle.lineTo(start + marker, top + marker); triangle.close();
            canvas.drawPath(triangle, paint);
            canvas.restore();
        }
        @Override public void setAlpha(int alpha) {}
        @Override public void setColorFilter(ColorFilter filter) {}
        @Override public int getOpacity() { return PixelFormat.TRANSLUCENT; }
    }
}
