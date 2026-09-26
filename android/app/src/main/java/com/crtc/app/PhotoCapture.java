package com.crtc.app;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.provider.MediaStore;
import androidx.core.content.FileProvider;
import java.io.File;

/**
 * Analyze-tab photo input. Upload Photo opens the Android image picker
 * (READ_MEDIA_IMAGES, falling back to READ_EXTERNAL_STORAGE on older APIs).
 * Take Photo opens the camera (CAMERA permission) writing through a
 * FileProvider. Permission denials surface an explanatory dialog instead of
 * failing silently. The chosen/captured photo URI is kept on MainActivity
 * (analysisPhoto) and shown as a thumbnail in the Analyze card.
 */
class PhotoCapture {
    static final int REQ_PICK = 1001;
    static final int REQ_TAKE = 1002;
    static final int REQ_PERM_PICK = 2001;
    static final int REQ_PERM_TAKE = 2002;

    static String pickPermission() {
        return Build.VERSION.SDK_INT >= 33
                ? Manifest.permission.READ_MEDIA_IMAGES
                : Manifest.permission.READ_EXTERNAL_STORAGE;
    }

    static void onUploadClicked(MainActivity a) {
        if (a.checkSelfPermission(pickPermission()) == PackageManager.PERMISSION_GRANTED) {
            openPicker(a);
        } else {
            a.requestPermissions(new String[]{pickPermission()}, REQ_PERM_PICK);
        }
    }

    static void openPicker(MainActivity a) {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.setType("image/*");
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        a.startActivityForResult(i, REQ_PICK);
    }

    static void onTakeClicked(MainActivity a) {
        if (a.checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            openCamera(a);
        } else {
            a.requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_PERM_TAKE);
        }
    }

    static void openCamera(MainActivity a) {
        try {
            File dir = new File(a.getCacheDir(), "photos");
            if (!dir.exists()) dir.mkdirs();
            File f = new File(dir, "photo_" + System.currentTimeMillis() + ".jpg");
            Uri uri = FileProvider.getUriForFile(a, a.getPackageName() + ".fileprovider", f);
            a.pendingPhotoUri = uri;
            Intent i = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
            i.putExtra(MediaStore.EXTRA_OUTPUT, uri);
            i.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            a.startActivityForResult(i, REQ_TAKE);
        } catch (Exception e) {
            a.infoDialog("Camera unavailable",
                    "Couldn't prepare the camera (" + e.getMessage() + "). Try Upload Photo instead.");
        }
    }

    /** Returns true when the result belonged to the photo flow. */
    static boolean onActivityResult(MainActivity a, int req, int res, Intent data) {
        if (req == REQ_PICK && res == Activity.RESULT_OK && data != null && data.getData() != null) {
            Uri u = data.getData();
            try {
                a.getContentResolver().takePersistableUriPermission(u,
                        Intent.FLAG_GRANT_READ_URI_PERMISSION);
            } catch (Exception ignored) { }
            a.analysisPhoto = u.toString();
            a.refreshPhotoThumb();
            a.events.record("photo_attached", "source=gallery");
            return true;
        }
        if (req == REQ_TAKE && res == Activity.RESULT_OK && a.pendingPhotoUri != null) {
            a.analysisPhoto = a.pendingPhotoUri.toString();
            a.pendingPhotoUri = null;
            a.refreshPhotoThumb();
            a.events.record("photo_attached", "source=camera");
            return true;
        }
        return false;
    }

    /** Returns true when the permission request belonged to the photo flow. */
    static boolean onPermissionResult(MainActivity a, int req, boolean granted) {
        if (req == REQ_PERM_PICK) {
            if (granted) {
                openPicker(a);
            } else {
                a.infoDialog("Photo access needed",
                        "Appraze needs access to your photo library to attach pictures to a deal analysis. "
                        + "Nothing is uploaded \u2014 the photo stays on this device. You can enable access "
                        + "anytime in Android Settings > Apps > Appraze > Permissions.");
            }
            return true;
        }
        if (req == REQ_PERM_TAKE) {
            if (granted) {
                openCamera(a);
            } else {
                a.infoDialog("Camera access needed",
                        "Appraze needs camera access to take deal photos. "
                        + "Nothing is uploaded \u2014 the photo stays on this device. You can enable access "
                        + "anytime in Android Settings > Apps > Appraze > Permissions.");
            }
            return true;
        }
        return false;
    }
}
